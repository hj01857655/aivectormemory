from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class CheckItem:
    name: str
    status: str  # pass / warn / fail
    detail: str
    fix: str = ""


def evaluate_codex_transport(transport: dict[str, Any]) -> list[CheckItem]:
    checks: list[CheckItem] = []
    cmd = str(transport.get("command") or "")
    args = [str(x) for x in (transport.get("args") or [])]

    if not cmd:
        checks.append(CheckItem("transport.command", "fail", "缺少 command", "重新注册 MCP：codex mcp add ..."))
        return checks

    if cmd == "uvx":
        checks.append(CheckItem("transport.command", "pass", "command=uvx"))
        if "-q" in args and "--no-progress" in args:
            checks.append(CheckItem("uvx.quiet", "pass", "已启用 -q --no-progress"))
        else:
            checks.append(
                CheckItem(
                    "uvx.quiet",
                    "fail",
                    "未启用静默参数，可能污染 stdio 协议流",
                    "改为：uvx -q --no-progress --from aivectormemory@latest run --project-dir .",
                )
            )
        if "--from" in args:
            checks.append(CheckItem("uvx.from", "pass", "已设置 --from"))
        else:
            checks.append(
                CheckItem(
                    "uvx.from",
                    "warn",
                    "未设置 --from，版本来源不明确",
                    "建议加：--from aivectormemory@latest",
                )
            )
    elif cmd == "run":
        checks.append(
            CheckItem(
                "transport.command",
                "warn",
                "command=run（依赖 PATH 中存在 run，可移植性较弱）",
                "建议改为 uvx 或 python -m aivectormemory。",
            )
        )
    else:
        checks.append(
            CheckItem(
                "transport.command",
                "warn",
                f"command={cmd}",
                "确认该命令在当前 shell 可执行，且不会向 stdout 输出非 JSON 文本。",
            )
        )

    if "--project-dir" not in args:
        checks.append(
            CheckItem(
                "project_dir.arg",
                "fail",
                "未配置 --project-dir",
                "建议追加：--project-dir .（按当前目录动态分项目）",
            )
        )
        return checks

    idx = args.index("--project-dir")
    value = args[idx + 1] if idx + 1 < len(args) else ""
    if value == ".":
        checks.append(CheckItem("project_dir.value", "pass", "--project-dir .（动态目录）"))
    elif value:
        checks.append(
            CheckItem(
                "project_dir.value",
                "warn",
                f"--project-dir {value}（固定目录）",
                "若希望跨项目复用同一配置，建议改为 --project-dir .",
            )
        )
    else:
        checks.append(
            CheckItem(
                "project_dir.value",
                "fail",
                "--project-dir 缺少取值",
                "请补全参数值（推荐 .）",
            )
        )
    return checks


def _run_capture(cmd: list[str], timeout_sec: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_sec,
        check=False,
    )


def _parse_json_lines(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    payloads: list[dict[str, Any]] = []
    noise: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            noise.append(line)
            continue
        if isinstance(obj, dict):
            payloads.append(obj)
        else:
            noise.append(line)
    return payloads, noise


def _probe_stdio_mcp(
    command: str,
    args: list[str],
    cwd: str | None,
    timeout_sec: int,
) -> tuple[list[CheckItem], dict[str, Any]]:
    checks: list[CheckItem] = []
    details: dict[str, Any] = {"command": command, "args": args, "cwd": cwd}

    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "aivm-doctor", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "status", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "auto_save", "arguments": {}}},
    ]
    payload = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in requests)

    env = os.environ.copy()
    try:
        cp = subprocess.run(
            [command, *args],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            check=False,
            cwd=cwd,
            env=env,
        )
    except FileNotFoundError:
        checks.append(
            CheckItem(
                "probe.spawn",
                "fail",
                f"无法启动命令：{command}",
                "检查命令是否存在，或重新执行 codex mcp add。",
            )
        )
        return checks, details
    except subprocess.TimeoutExpired:
        checks.append(
            CheckItem(
                "probe.timeout",
                "fail",
                f"探针超时（>{timeout_sec}s）",
                "检查网络/依赖初始化，或提高 --timeout。",
            )
        )
        return checks, details

    details["returncode"] = cp.returncode
    details["stderr"] = cp.stderr.strip()

    payloads, noise = _parse_json_lines(cp.stdout)
    details["json_lines"] = len(payloads)
    details["noise_lines"] = noise[:20]
    if noise:
        checks.append(
            CheckItem(
                "probe.stdout_noise",
                "warn",
                f"stdout 检测到 {len(noise)} 行非 JSON 文本",
                "若频繁出现，建议强制使用 uvx -q --no-progress。",
            )
        )
    else:
        checks.append(CheckItem("probe.stdout_noise", "pass", "stdout 无非 JSON 噪声"))

    responses: dict[int, dict[str, Any]] = {}
    for obj in payloads:
        req_id = obj.get("id")
        if isinstance(req_id, int):
            responses[req_id] = obj

    def _check_response(req_id: int, name: str) -> None:
        obj = responses.get(req_id)
        if not obj:
            checks.append(CheckItem(name, "fail", f"未收到 id={req_id} 响应"))
            return
        if "error" in obj:
            msg = str((obj.get("error") or {}).get("message") or obj.get("error"))
            checks.append(CheckItem(name, "fail", f"响应报错：{msg}"))
            return
        checks.append(CheckItem(name, "pass", "响应正常"))

    _check_response(1, "probe.initialize")
    _check_response(2, "probe.tools_list")
    _check_response(3, "probe.status")
    _check_response(4, "probe.auto_save")

    tools = []
    tools_obj = responses.get(2, {}).get("result", {}).get("tools", [])
    if isinstance(tools_obj, list):
        tools = [str(item.get("name")) for item in tools_obj if isinstance(item, dict)]
    if "status" in tools and "auto_save" in tools:
        checks.append(CheckItem("probe.tools_expected", "pass", "status/auto_save 工具可见"))
    else:
        checks.append(
            CheckItem(
                "probe.tools_expected",
                "fail",
                f"tools/list 缺少预期工具，当前={tools}",
            )
        )

    if cp.returncode == 0:
        checks.append(CheckItem("probe.exit_code", "pass", "进程退出码=0"))
    else:
        checks.append(
            CheckItem(
                "probe.exit_code",
                "warn",
                f"进程退出码={cp.returncode}",
                "若响应均通过可先继续使用；若有失败项，请按修复建议调整配置。",
            )
        )
    return checks, details


def run_doctor_codex(
    *,
    server_name: str = "aivectormemory",
    no_probe: bool = False,
    timeout_sec: int = 25,
    json_output: bool = False,
) -> int:
    checks: list[CheckItem] = []
    report: dict[str, Any] = {"server_name": server_name}

    codex_bin = shutil.which("codex")
    if not codex_bin:
        checks.append(CheckItem("codex.binary", "fail", "未找到 codex 命令", "请先安装 Codex CLI 并确保 PATH 可用。"))
        report["checks"] = [asdict(x) for x in checks]
        _print_report(report, json_output)
        return 1
    checks.append(CheckItem("codex.binary", "pass", f"codex 命令可用：{codex_bin}"))

    try:
        cp = _run_capture([codex_bin, "mcp", "get", server_name, "--json"], timeout_sec=timeout_sec)
    except FileNotFoundError:
        checks.append(
            CheckItem(
                "codex.mcp.get",
                "fail",
                f"执行失败，无法启动：{codex_bin}",
                "请检查 codex 安装完整性，或重新安装 Codex CLI。",
            )
        )
        report["checks"] = [asdict(x) for x in checks]
        _print_report(report, json_output)
        return 1
    report["codex_get_rc"] = cp.returncode
    if cp.returncode != 0:
        checks.append(
            CheckItem(
                "codex.mcp.get",
                "fail",
                f"读取配置失败：{cp.stderr.strip() or cp.stdout.strip()}",
                f"请先执行：codex mcp add {server_name} -- uvx -q --no-progress --from aivectormemory@latest run --project-dir .",
            )
        )
        report["checks"] = [asdict(x) for x in checks]
        _print_report(report, json_output)
        return 1

    try:
        config = json.loads(cp.stdout)
    except json.JSONDecodeError:
        checks.append(CheckItem("codex.mcp.get", "fail", "输出不是合法 JSON", "请手动执行 codex mcp get ... --json 检查。"))
        report["raw_stdout"] = cp.stdout[:2000]
        report["checks"] = [asdict(x) for x in checks]
        _print_report(report, json_output)
        return 1

    report["config"] = config
    if config.get("enabled") is True:
        checks.append(CheckItem("config.enabled", "pass", "enabled=true"))
    else:
        checks.append(CheckItem("config.enabled", "fail", "enabled 不是 true", "执行：codex mcp enable aivectormemory"))

    transport = config.get("transport") or {}
    if str(transport.get("type") or "") == "stdio":
        checks.append(CheckItem("transport.type", "pass", "transport=stdio"))
    else:
        checks.append(CheckItem("transport.type", "fail", f"transport={transport.get('type')}", "请改为 stdio MCP。"))

    checks.extend(evaluate_codex_transport(transport))

    probe_details: dict[str, Any] = {}
    if not no_probe and transport:
        command = str(transport.get("command") or "")
        args = [str(x) for x in (transport.get("args") or [])]
        cwd = transport.get("cwd")
        probe_checks, probe_details = _probe_stdio_mcp(command, args, cwd=cwd, timeout_sec=timeout_sec)
        checks.extend(probe_checks)
    report["probe"] = probe_details

    report["checks"] = [asdict(x) for x in checks]
    _print_report(report, json_output)
    has_fail = any(x.status == "fail" for x in checks)
    return 1 if has_fail else 0


def _print_report(report: dict[str, Any], json_output: bool) -> None:
    checks = [CheckItem(**x) for x in report.get("checks", [])]
    if json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("AIVectorMemory Codex Doctor")
    print("=" * 32)
    for item in checks:
        icon = {"pass": "OK", "warn": "WARN", "fail": "FAIL"}.get(item.status, item.status.upper())
        print(f"[{icon}] {item.name}: {item.detail}")
        if item.fix:
            print(f"      fix: {item.fix}")
    total = len(checks)
    fail = sum(1 for x in checks if x.status == "fail")
    warn = sum(1 for x in checks if x.status == "warn")
    ok = sum(1 for x in checks if x.status == "pass")
    print("-" * 32)
    print(f"summary: total={total} pass={ok} warn={warn} fail={fail}")
    if fail == 0:
        print("result: READY")
    else:
        print("result: NOT_READY")
