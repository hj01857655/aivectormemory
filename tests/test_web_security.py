import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from urllib import error, request

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]


def _python_for_web() -> str:
    candidates = [
        ROOT_DIR / ".venv" / "Scripts" / "python.exe",
        ROOT_DIR / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _http_json(url: str, method: str = "GET", body: dict | None = None, headers: dict | None = None, timeout: int = 5):
    req_headers = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = request.Request(url, data=data, method=method, headers=req_headers)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "ignore")
        payload = {}
        if raw:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"raw": raw}
        return exc.code, payload


def _wait_server_ready(base_url: str, process: subprocess.Popen, timeout_seconds: int = 20):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if process.poll() is not None:
            out, err = process.communicate()
            raise RuntimeError(f"web server exited early: {process.returncode}\nstdout:\n{out}\nstderr:\n{err}")
        try:
            request.urlopen(f"{base_url}/", timeout=1)
            return
        except Exception:
            time.sleep(0.3)
    raise TimeoutError("web server did not become ready in time")


@contextmanager
def _run_web(token: str | None = None, project_dir: str | None = None, db_dir: str | None = None):
    port = _free_port()
    with ExitStack() as stack:
        local_project_dir = project_dir or stack.enter_context(tempfile.TemporaryDirectory(prefix="avm-sec-test-proj-"))
        local_db_dir = db_dir or stack.enter_context(tempfile.TemporaryDirectory(prefix="avm-sec-test-db-"))
        python_bin = _python_for_web()
        cmd = [
            python_bin,
            "-m",
            "aivectormemory",
            "web",
            "--project-dir",
            local_project_dir,
            "--port",
            str(port),
            "--bind",
            "127.0.0.1",
            "--quiet",
        ]
        if token:
            cmd.extend(["--token", token])
        env = os.environ.copy()
        env["AIVM_DB_DIR"] = local_db_dir
        process = subprocess.Popen(
            cmd,
            cwd=ROOT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            _wait_server_ready(base_url, process)
            yield base_url
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
            # uv on Windows may leave child processes alive; force kill the full tree to release DB file locks.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            time.sleep(0.2)


def _register_and_login(base_url: str, username: str, password: str, extra_headers: dict | None = None) -> str:
    headers = extra_headers or {}
    status, payload = _http_json(
        f"{base_url}/api/auth/register",
        method="POST",
        body={"username": username, "password": password},
        headers=headers,
    )
    assert status == 200, payload

    status, payload = _http_json(
        f"{base_url}/api/auth/login",
        method="POST",
        body={"username": username, "password": password},
        headers=headers,
    )
    assert status == 200, payload
    token = payload.get("token")
    assert token
    return token


def test_api_requires_bearer_auth():
    with _run_web() as base_url:
        status, _ = _http_json(f"{base_url}/api/projects")
        assert status == 401

        token = _register_and_login(base_url, "sec_user_01", "Strong#Pass1234")
        status, payload = _http_json(
            f"{base_url}/api/projects",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert "projects" in payload


def test_static_path_traversal_is_blocked():
    with _run_web() as base_url:
        status_1, _ = _http_json(f"{base_url}/../README.md")
        status_2, _ = _http_json(f"{base_url}/%2e%2e/%2e%2e/README.md")
        assert status_1 == 403
        assert status_2 == 403


def test_server_token_header_is_enforced():
    with _run_web(token="server-secret-123") as base_url:
        status_no_header, _ = _http_json(
            f"{base_url}/api/auth/register",
            method="POST",
            body={"username": "sec_user_02", "password": "Strong#Pass1234"},
        )
        assert status_no_header == 403

        status_with_header, payload = _http_json(
            f"{base_url}/api/auth/register",
            method="POST",
            body={"username": "sec_user_02", "password": "Strong#Pass1234"},
            headers={"X-AVM-Server-Token": "server-secret-123"},
        )
        assert status_with_header == 200
        assert payload.get("success") is True


def test_password_policy_and_rate_limit():
    with _run_web() as base_url:
        status, payload = _http_json(
            f"{base_url}/api/auth/register",
            method="POST",
            body={"username": "sec_user_03", "password": "abc123"},
        )
        assert status == 200
        assert "at least 12" in payload.get("error", "")

        _register_and_login(base_url, "sec_user_04", "Strong#Pass1234")

        for _ in range(5):
            status, payload = _http_json(
                f"{base_url}/api/auth/login",
                method="POST",
                body={"username": "sec_user_04", "password": "Wrong#Pass1234"},
            )
            assert status == 200
            assert "error" in payload

        status, payload = _http_json(
            f"{base_url}/api/auth/login",
            method="POST",
            body={"username": "sec_user_04", "password": "Wrong#Pass1234"},
        )
        assert status == 200
        assert "too many attempts" in payload.get("error", "")


def test_session_and_rate_limit_persist_across_restart():
    with tempfile.TemporaryDirectory(prefix="avm-sec-shared-proj-") as project_dir, tempfile.TemporaryDirectory(prefix="avm-sec-shared-db-") as db_dir:
        with _run_web(project_dir=project_dir, db_dir=db_dir) as base_url:
            token = _register_and_login(base_url, "sec_user_05", "Strong#Pass1234")
            for _ in range(5):
                status, payload = _http_json(
                    f"{base_url}/api/auth/login",
                    method="POST",
                    body={"username": "sec_user_05", "password": "Wrong#Pass1234"},
                )
                assert status == 200
                assert "error" in payload

        with _run_web(project_dir=project_dir, db_dir=db_dir) as base_url:
            status, payload = _http_json(
                f"{base_url}/api/projects",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert status == 200
            assert "projects" in payload

            status, payload = _http_json(
                f"{base_url}/api/auth/login",
                method="POST",
                body={"username": "sec_user_05", "password": "Wrong#Pass1234"},
            )
            assert status == 200
            assert "too many attempts" in payload.get("error", "")
