"""验证 _merge_config 能正确清理旧 devmemory key"""
import json
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aivectormemory.install import _merge_config

def test_removes_old_devmemory_key():
    """旧配置有 devmemory key，merge 后应该被删除"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        old_config = {"mcpServers": {"devmemory": {"command": "old", "args": []}}}
        json.dump(old_config, f)
        f.flush()
        fp = Path(f.name)

    new_server = {"command": "run", "args": ["--project-dir", "/test"]}
    changed = _merge_config(fp, "mcpServers", "aivectormemory", new_server)

    result = json.loads(fp.read_text("utf-8"))
    assert changed, "应该返回 True 表示有变更"
    assert "aivectormemory" in result["mcpServers"], "新 key 应该存在"
    assert "devmemory" not in result["mcpServers"], "旧 devmemory key 应该被删除"
    print("✓ test_removes_old_devmemory_key PASSED")
    fp.unlink()

def test_no_old_key_no_error():
    """全新安装，没有旧 key，不应报错"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({}, f)
        f.flush()
        fp = Path(f.name)

    new_server = {"command": "run", "args": ["--project-dir", "/test"]}
    changed = _merge_config(fp, "mcpServers", "aivectormemory", new_server)

    result = json.loads(fp.read_text("utf-8"))
    assert changed, "应该返回 True"
    assert "aivectormemory" in result["mcpServers"]
    assert "devmemory" not in result["mcpServers"]
    print("✓ test_no_old_key_no_error PASSED")
    fp.unlink()

def test_idempotent():
    """相同配置再次写入应返回 False"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({}, f)
        f.flush()
        fp = Path(f.name)

    new_server = {"command": "run", "args": ["--project-dir", "/test"]}
    _merge_config(fp, "mcpServers", "aivectormemory", new_server)
    changed = _merge_config(fp, "mcpServers", "aivectormemory", new_server)

    assert not changed, "相同配置不应有变更"
    print("✓ test_idempotent PASSED")
    fp.unlink()

def test_opencode_format():
    """OpenCode 格式用 mcp key 而非 mcpServers"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        old_config = {"mcp": {"devmemory": {"type": "local", "command": ["old"], "enabled": True}}}
        json.dump(old_config, f)
        f.flush()
        fp = Path(f.name)

    new_server = {"type": "local", "command": ["run", "--project-dir", "/test"], "enabled": True}
    changed = _merge_config(fp, "mcp", "aivectormemory", new_server)

    result = json.loads(fp.read_text("utf-8"))
    assert changed
    assert "aivectormemory" in result["mcp"]
    assert "devmemory" not in result["mcp"], "OpenCode 格式下旧 key 也应被删除"
    print("✓ test_opencode_format PASSED")
    fp.unlink()

if __name__ == "__main__":
    test_removes_old_devmemory_key()
    test_no_old_key_no_error()
    test_idempotent()
    test_opencode_format()
    print("\n全部测试通过")
