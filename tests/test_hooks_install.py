"""测试 install.py 中各 IDE hooks 配置生成"""
import json
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from aivectormemory.install import (
    _write_claude_code_hooks,
    _write_cursor_hooks,
    _write_windsurf_hooks,
    _write_hooks,
    _write_opencode_plugins,
    CLAUDE_CODE_HOOKS_CONFIG,
    CURSOR_HOOKS_CONFIG,
    WINDSURF_HOOKS_CONFIG,
)


def test_claude_code_hooks():
    with tempfile.TemporaryDirectory() as tmpdir:
        hooks_dir = Path(tmpdir) / ".claude"
        results = _write_claude_code_hooks(hooks_dir)
        assert any("✓ 已生成" in r for r in results), f"首次写入应该生成: {results}"
        settings = json.loads((hooks_dir / "settings.json").read_text("utf-8"))
        assert "hooks" in settings
        assert "PreToolUse" in settings["hooks"]
        assert "UserPromptSubmit" in settings["hooks"], "应包含 UserPromptSubmit hook"
        ups_hook = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]
        assert ups_hook["type"] == "command", "UserPromptSubmit 应为 command 类型"
        assert "inject-workflow-rules" in ups_hook["command"], "应指向 inject-workflow-rules.sh"
        # 验证 inject 脚本生成
        inject_script = hooks_dir / "hooks" / "inject-workflow-rules.sh"
        assert inject_script.exists(), "inject-workflow-rules.sh 应存在"
        inject_content = inject_script.read_text("utf-8")
        assert "IDENTITY" in inject_content, "inject 脚本应包含 IDENTITY 规则"
        assert "Stop" not in settings["hooks"], "Stop hook 应已删除"
        # 幂等性
        results2 = _write_claude_code_hooks(hooks_dir)
        assert any("无变更" in r for r in results2), f"重复写入应无变更: {results2}"
        # 保留已有配置
        settings["customKey"] = "test"
        (hooks_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        results3 = _write_claude_code_hooks(hooks_dir)
        updated = json.loads((hooks_dir / "settings.json").read_text("utf-8"))
        assert updated.get("customKey") == "test", "应保留已有配置"
        # 清理旧 Stop hook
        settings["hooks"]["Stop"] = [{"hooks": [{"type": "prompt", "prompt": "old"}]}]
        (hooks_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        results4 = _write_claude_code_hooks(hooks_dir)
        assert any("✓ 已生成" in r for r in results4), f"有旧 Stop hook 应重新生成: {results4}"
        cleaned = json.loads((hooks_dir / "settings.json").read_text("utf-8"))
        assert "Stop" not in cleaned["hooks"], "旧 Stop hook 应被清理"
    print("✅ Claude Code hooks 测试通过")


def test_cursor_hooks():
    with tempfile.TemporaryDirectory() as tmpdir:
        hooks_dir = Path(tmpdir) / ".cursor"
        results = _write_cursor_hooks(hooks_dir)
        assert any("✓ 已生成" in r for r in results), f"首次写入应该生成: {results}"
        config = json.loads((hooks_dir / "hooks.json").read_text("utf-8"))
        assert config["version"] == 1
        assert "preToolUse" in config["hooks"], "应包含 preToolUse hook"
        assert "beforeSubmitPrompt" not in config["hooks"], "旧 beforeSubmitPrompt hook 应已清理"
        # 幂等性
        results2 = _write_cursor_hooks(hooks_dir)
        assert any("无变更" in r for r in results2), f"重复写入应无变更: {results2}"
    print("✅ Cursor hooks 测试通过")


def test_windsurf_hooks():
    with tempfile.TemporaryDirectory() as tmpdir:
        hooks_dir = Path(tmpdir) / ".windsurf"
        results = _write_windsurf_hooks(hooks_dir)
        assert any("✓ 已生成" in r for r in results), f"首次写入应该生成: {results}"
        config = json.loads((hooks_dir / "hooks.json").read_text("utf-8"))
        assert "hooks" in config
        assert "pre_write_code" in config["hooks"], "应包含 pre_write_code hook"
        # 幂等性
        results2 = _write_windsurf_hooks(hooks_dir)
        assert any("无变更" in r for r in results2), f"重复写入应无变更: {results2}"
    print("✅ Windsurf hooks 测试通过")


def test_kiro_hooks():
    with tempfile.TemporaryDirectory() as tmpdir:
        hooks_dir = Path(tmpdir) / ".kiro" / "hooks"
        results = _write_hooks(hooks_dir)
        assert any("✓ 已生成" in r for r in results), f"首次写入应该生成: {results}"
        assert (hooks_dir / "dev-workflow-check.kiro.hook").exists()
        assert (hooks_dir / "pre-tool-use-check.kiro.hook").exists()
        assert not (hooks_dir / "auto-save-session.kiro.hook").exists(), "auto-save hook 应已删除"
        # 验证 dev-workflow-check 包含 IDENTITY & TONE 但不含链式防护
        content = json.loads((hooks_dir / "dev-workflow-check.kiro.hook").read_text("utf-8"))
        assert "链式触发防护" not in content["then"]["prompt"], "不应包含链式防护"
        assert "IDENTITY & TONE" in content["then"]["prompt"], "应包含 IDENTITY & TONE"
        assert "消息类型判断" in content["then"]["prompt"], "应包含消息类型判断"
        assert "验证相应文件代码后回答" in content["then"]["prompt"], "应包含'验证相应文件代码后回答'措辞"
        # 幂等性
        results2 = _write_hooks(hooks_dir)
        assert all("无变更" in r for r in results2), f"重复写入应无变更: {results2}"
    print("✅ Kiro hooks 测试通过")


def test_opencode_plugins():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / ".opencode" / "plugins"
        results = _write_opencode_plugins(plugins_dir)
        assert any("✓ 已生成" in r for r in results), f"首次写入应该生成: {results}"
        assert (plugins_dir / "aivectormemory-pre-tool-check.js").exists()
        content = (plugins_dir / "aivectormemory-pre-tool-check.js").read_text("utf-8")
        assert "tool.execute.before" in content
        assert "experimental.chat.system.transform" in content, "应包含 system.transform 注入"
        assert "DEV_WORKFLOW_RULES" in content, "应包含 DEV_WORKFLOW_RULES"
        assert "IDENTITY" in content, "应包含 IDENTITY 规则内容"
        assert "session.stop" not in content, "不应包含 session.stop event handler"
        # 幂等性
        results2 = _write_opencode_plugins(plugins_dir)
        assert any("无变更" in r for r in results2), f"重复写入应无变更: {results2}"
    print("✅ OpenCode plugins 测试通过")


if __name__ == "__main__":
    test_claude_code_hooks()
    test_cursor_hooks()
    test_windsurf_hooks()
    test_kiro_hooks()
    test_opencode_plugins()
    print("\n🎉 所有 hooks 测试通过")
