import json
import os
import shutil
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
EMBEDDING_384 = [0.0] * 384


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


def _wait_server_ready(base_url: str, process: subprocess.Popen, timeout_seconds: int = 40):
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
        env["AIVM_DISABLE_EMBEDDING"] = "1"
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
            # Windows 进程树清理：避免残留子进程占用 SQLite 文件；非 Windows 不执行 taskkill。
            if os.name == "nt" and shutil.which("taskkill"):
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


def test_password_change_revokes_existing_sessions():
    with _run_web() as base_url:
        token = _register_and_login(base_url, "sec_user_06", "Strong#Pass1234")
        status, payload = _http_json(
            f"{base_url}/api/auth/change-password",
            method="POST",
            headers={"Authorization": f"Bearer {token}"},
            body={
                "current_password": "Strong#Pass1234",
                "new_password": "Strong#Pass5678",
            },
        )
        assert status == 200
        assert payload.get("success") is True

        # 改密后旧 token 必须立刻失效。
        status, _ = _http_json(
            f"{base_url}/api/projects",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 401

        status, payload = _http_json(
            f"{base_url}/api/auth/login",
            method="POST",
            body={"username": "sec_user_06", "password": "Strong#Pass5678"},
        )
        assert status == 200
        assert payload.get("token")


def test_project_access_isolation_between_users():
    from urllib.parse import quote

    with _run_web() as base_url:
        token_a = _register_and_login(base_url, "sec_user_07", "Strong#Pass1234")
        private_project = "E:/VSCodeSpace/private-alpha"

        status, payload = _http_json(
            f"{base_url}/api/projects",
            method="POST",
            headers={"Authorization": f"Bearer {token_a}"},
            body={"project_dir": private_project},
        )
        assert status == 200, payload
        assert payload.get("success") is True

        status, _ = _http_json(
            f"{base_url}/api/status?project={quote(private_project, safe='')}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert status == 200

        token_b = _register_and_login(base_url, "sec_user_08", "Strong#Pass1234")
        status, payload = _http_json(
            f"{base_url}/api/projects",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert status == 200, payload
        names = {p["project_dir"] for p in payload.get("projects", [])}
        assert private_project not in names

        status, _ = _http_json(
            f"{base_url}/api/status?project={quote(private_project, safe='')}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert status == 403

        encoded = quote(private_project, safe="")
        status, _ = _http_json(
            f"{base_url}/api/projects/{encoded}",
            method="DELETE",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert status == 403


def test_public_bind_requires_server_token():
    with tempfile.TemporaryDirectory(prefix="avm-bind-guard-") as project_dir:
        with tempfile.TemporaryDirectory(prefix="avm-bind-guard-db-") as db_dir:
            cmd = [
                _python_for_web(),
                "-m",
                "aivectormemory",
                "web",
                "--project-dir",
                project_dir,
                "--port",
                str(_free_port()),
                "--bind",
                "0.0.0.0",
                "--quiet",
            ]
            env = os.environ.copy()
            env["AIVM_DB_DIR"] = db_dir
            env["AIVM_DISABLE_EMBEDDING"] = "1"
            proc = subprocess.run(
                cmd,
                cwd=ROOT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                timeout=10,
                check=False,
            )
            assert proc.returncode != 0
            combined = f"{proc.stdout}\n{proc.stderr}".lower()
            assert "refusing non-loopback bind without server token" in combined


def test_scope_all_memories_and_export_do_not_leak_private_project():
    from urllib.parse import quote

    with _run_web() as base_url:
        private_project = "E:/VSCodeSpace/private-sec-01"
        token_a = _register_and_login(base_url, "sec_user_09", "Strong#Pass1234")
        status, payload = _http_json(
            f"{base_url}/api/projects",
            method="POST",
            headers={"Authorization": f"Bearer {token_a}"},
            body={"project_dir": private_project},
        )
        assert status == 200, payload
        assert payload.get("success") is True

        status, payload = _http_json(
            f"{base_url}/api/import",
            method="POST",
            headers={"Authorization": f"Bearer {token_a}"},
            body={
                "memories": [
                    {
                        "id": "sec_priv_mem_01",
                        "content": "private content",
                        "tags": ["private"],
                        "scope": "project",
                        "project_dir": private_project,
                        "embedding": EMBEDDING_384,
                    }
                ]
            },
        )
        assert status == 200, payload
        assert payload.get("imported") == 1

        token_b = _register_and_login(base_url, "sec_user_10", "Strong#Pass1234")
        encoded = quote(private_project, safe="")
        status, _ = _http_json(
            f"{base_url}/api/status?project={encoded}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert status == 403

        status, payload = _http_json(
            f"{base_url}/api/memories?scope=all&limit=100",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert status == 200, payload
        leaked = [m for m in payload.get("memories", []) if m.get("project_dir") == private_project]
        assert leaked == []

        status, payload = _http_json(
            f"{base_url}/api/export?scope=all",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert status == 200, payload
        leaked = [m for m in payload.get("memories", []) if m.get("project_dir") == private_project]
        assert leaked == []


def test_import_rejects_forbidden_project_dir():
    from urllib.parse import quote

    with _run_web() as base_url:
        private_project = "E:/VSCodeSpace/private-sec-02"
        token_a = _register_and_login(base_url, "sec_user_11", "Strong#Pass1234")
        status, payload = _http_json(
            f"{base_url}/api/projects",
            method="POST",
            headers={"Authorization": f"Bearer {token_a}"},
            body={"project_dir": private_project},
        )
        assert status == 200, payload
        assert payload.get("success") is True

        token_b = _register_and_login(base_url, "sec_user_12", "Strong#Pass1234")
        status, payload = _http_json(
            f"{base_url}/api/import",
            method="POST",
            headers={"Authorization": f"Bearer {token_b}"},
            body={
                "memories": [
                    {
                        "id": "sec_forbidden_mem_01",
                        "content": "inject private project",
                        "tags": ["attack"],
                        "scope": "project",
                        "project_dir": private_project,
                        "embedding": EMBEDDING_384,
                    }
                ]
            },
        )
        assert status == 200, payload
        assert payload.get("imported") == 0
        assert payload.get("skipped") == 1
        errors = payload.get("errors") or []
        assert errors
        assert errors[0].get("error") == "forbidden project_dir"

        encoded = quote(private_project, safe="")
        status, payload = _http_json(
            f"{base_url}/api/memories?scope=project&project={encoded}&limit=100",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert status == 200, payload
        ids = {m.get("id") for m in payload.get("memories", [])}
        assert "sec_forbidden_mem_01" not in ids


def test_import_invalid_embedding_returns_structured_error():
    with _run_web() as base_url:
        token = _register_and_login(base_url, "sec_user_13", "Strong#Pass1234")
        status, payload = _http_json(
            f"{base_url}/api/import",
            method="POST",
            headers={"Authorization": f"Bearer {token}"},
            body={
                "memories": [
                    {
                        "id": "sec_bad_embedding_01",
                        "content": "bad embedding",
                        "tags": ["bad"],
                        "scope": "project",
                        "embedding": [0.1, 0.2],
                    }
                ]
            },
        )
        assert status == 200, payload
        assert payload.get("imported") == 0
        assert payload.get("skipped") == 1
        errors = payload.get("errors") or []
        assert errors
        assert "invalid embedding" in errors[0].get("error", "")


def test_user_scope_memories_are_isolated_between_users():
    with _run_web() as base_url:
        token_a = _register_and_login(base_url, "sec_user_14", "Strong#Pass1234")
        status, payload = _http_json(
            f"{base_url}/api/import",
            method="POST",
            headers={"Authorization": f"Bearer {token_a}"},
            body={
                "memories": [
                    {
                        "id": "sec_user_scope_mem_01",
                        "content": "user a private preference",
                        "tags": ["preference"],
                        "scope": "user",
                        "embedding": EMBEDDING_384,
                    }
                ]
            },
        )
        assert status == 200, payload
        assert payload.get("imported") == 1

        status, payload = _http_json(
            f"{base_url}/api/memories?scope=user&limit=50",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert status == 200, payload
        ids = {m.get("id") for m in payload.get("memories", [])}
        assert "sec_user_scope_mem_01" in ids

        token_b = _register_and_login(base_url, "sec_user_15", "Strong#Pass1234")
        status, payload = _http_json(
            f"{base_url}/api/memories?scope=user&limit=50",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert status == 200, payload
        ids = {m.get("id") for m in payload.get("memories", [])}
        assert "sec_user_scope_mem_01" not in ids

        status, payload = _http_json(
            f"{base_url}/api/memories?scope=all&limit=50",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert status == 200, payload
        ids = {m.get("id") for m in payload.get("memories", [])}
        assert "sec_user_scope_mem_01" not in ids

        status, payload = _http_json(
            f"{base_url}/api/stats",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert status == 200, payload
        assert payload.get("memories", {}).get("user", -1) == 0
