"""验证 STEERING_CONTENT 更新后，_write_steering 能正确检测变化并更新"""
from pathlib import Path
import tempfile
from aivectormemory.install import _write_steering, STEERING_CONTENT, STEERING_MARKER

def test_file_mode_creates():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "test.md"
        assert _write_steering(f, "file") is True
        assert "新会话启动" in f.read_text("utf-8")

def test_file_mode_no_change():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "test.md"
        _write_steering(f, "file")
        assert _write_steering(f, "file") is False

def test_append_mode_creates():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "CLAUDE.md"
        f.write_text("# My Project\n", "utf-8")
        assert _write_steering(f, "append") is True
        content = f.read_text("utf-8")
        assert "# My Project" in content
        assert "新会话启动" in content

def test_append_mode_updates_old_content():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "CLAUDE.md"
        old = f"# My Project\n\n{STEERING_MARKER}\n# Old content\n"
        f.write_text(old, "utf-8")
        assert _write_steering(f, "append") is True
        content = f.read_text("utf-8")
        assert "Old content" not in content
        assert "新会话启动" in content

def test_append_mode_no_change():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "CLAUDE.md"
        _write_steering(f, "append")
        assert _write_steering(f, "append") is False

def test_content_has_all_sections():
    assert "新会话启动" in STEERING_CONTENT
    assert "阻塞规则" in STEERING_CONTENT
    assert "记忆质量要求" in STEERING_CONTENT
    assert "问题追踪" in STEERING_CONTENT
    assert "工具速查" in STEERING_CONTENT
    assert "开发规范" in STEERING_CONTENT

if __name__ == "__main__":
    test_file_mode_creates()
    test_file_mode_no_change()
    test_append_mode_creates()
    test_append_mode_updates_old_content()
    test_append_mode_no_change()
    test_content_has_all_sections()
    print("All 6 steering update tests passed")
