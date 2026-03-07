"""协议层测试：通过 subprocess 模拟 stdio JSON-RPC 通信"""
import json
import subprocess
import tempfile
import os


def send_messages(messages: list[dict], project_dir: str) -> list[dict]:
    input_data = "\n".join(json.dumps(m) for m in messages) + "\n"
    env = {**os.environ, "HF_ENDPOINT": "https://hf-mirror.com"}
    proc = subprocess.run(
        [".venv/bin/python", "-m", "aivectormemory", "--project-dir", project_dir],
        input=input_data, capture_output=True, text=True, timeout=30, env=env
    )
    responses = []
    for line in proc.stdout.strip().split("\n"):
        if line.strip():
            responses.append(json.loads(line))
    return responses


def test_initialize_and_tools_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ]
        responses = send_messages(msgs, tmpdir)

        # initialize 响应
        assert responses[0]["id"] == 1
        result = responses[0]["result"]
        assert result["serverInfo"]["name"] == "aivectormemory"
        assert "tools" in result["capabilities"]

        # tools/list 响应
        assert responses[1]["id"] == 2
        tools = responses[1]["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "remember" in tool_names
        assert "recall" in tool_names
        assert "forget" in tool_names
        assert "status" in tool_names
        assert "track" in tool_names
        assert "auto_save" in tool_names
        assert "task" in tool_names
        assert "readme" in tool_names
        assert len(tools) == 8


def test_session_id_increments():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 第一次连接
        msgs1 = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        ]
        r1 = send_messages(msgs1, tmpdir)
        assert r1[0]["result"]["serverInfo"]["name"] == "aivectormemory"

        # 第二次连接（新进程，session_id 应该从 db 读取 max 后 +1）
        r2 = send_messages(msgs1, tmpdir)
        assert r2[0]["result"]["serverInfo"]["name"] == "aivectormemory"


def test_unknown_method():
    with tempfile.TemporaryDirectory() as tmpdir:
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "nonexistent/method", "params": {}},
        ]
        responses = send_messages(msgs, tmpdir)
        assert responses[1]["id"] == 2
        assert "error" in responses[1]
        assert responses[1]["error"]["code"] == -32601


def test_unknown_tool():
    with tempfile.TemporaryDirectory() as tmpdir:
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "nonexistent", "arguments": {}}},
        ]
        responses = send_messages(msgs, tmpdir)
        assert responses[1]["error"]["code"] == -32601


if __name__ == "__main__":
    test_initialize_and_tools_list()
    test_session_id_increments()
    test_unknown_method()
    test_unknown_tool()
    print("All protocol tests passed!")
