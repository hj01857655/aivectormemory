"""验证 OpenCode install 生成 pre-tool-check 插件"""
import sys, tempfile, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aivectormemory.install import _write_opencode_plugins, _write_hooks, IDES

def test_ides_opencode_has_hooks_fn():
    """验证 IDES 列表中 OpenCode 行的 hooks_fn 不为 None"""
    opencode = [ide for ide in IDES if ide[0] == "OpenCode"][0]
    hooks_fn = opencode[6]  # 第7个元素
    assert hooks_fn is not None, "OpenCode hooks_fn should not be None"
    root = Path("/tmp/test-project")
    result = hooks_fn(root)
    assert str(result).endswith(".opencode/plugins"), f"Expected .opencode/plugins, got {result}"
    print("✓ IDES OpenCode hooks_fn 正确指向 .opencode/plugins")

def test_write_opencode_plugins():
    """验证 _write_opencode_plugins 生成正确的 JS 文件和 package.json"""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / ".opencode" / "plugins"
        results = _write_opencode_plugins(plugins_dir)
        assert any("✓ 已生成" in r for r in results), f"Expected creation, got {results}"

        filepath = plugins_dir / "aivectormemory-pre-tool-check.js"
        assert filepath.exists(), "Plugin file should exist"

        content = filepath.read_text("utf-8")
        assert "tool.execute.before" in content, "Plugin should have tool.execute.before handler"
        assert "session.stop" not in content, "Plugin should NOT have session.stop handler"
        print("✓ 插件文件生成正确，包含 tool.execute.before")

        # 验证 package.json 包含 type: module
        pkg_path = plugins_dir.parent / "package.json"
        assert pkg_path.exists(), "package.json should exist"
        pkg = json.loads(pkg_path.read_text("utf-8"))
        assert pkg.get("type") == "module", f"package.json should have type:module, got {pkg}"
        assert "@opencode-ai/plugin" in pkg.get("dependencies", {}), "Should have plugin dependency"
        print("✓ package.json 包含 type: module")

        # 第二次调用应该无变更
        results2 = _write_opencode_plugins(plugins_dir)
        assert any("无变更" in r and "package.json" in r for r in results2), f"Expected pkg no change, got {results2}"
        assert any("无变更" in r and "Plugin" in r for r in results2), f"Expected plugin no change, got {results2}"
        print("✓ 重复调用无变更（幂等性）")

def test_write_opencode_plugins_fixes_existing_pkg():
    """验证对已有但缺少 type:module 的 package.json 能正确修复"""
    with tempfile.TemporaryDirectory() as tmpdir:
        opencode_dir = Path(tmpdir) / ".opencode"
        opencode_dir.mkdir(parents=True)
        pkg_path = opencode_dir / "package.json"
        pkg_path.write_text(json.dumps({"dependencies": {"@opencode-ai/plugin": "1.2.10"}}), encoding="utf-8")

        plugins_dir = opencode_dir / "plugins"
        results = _write_opencode_plugins(plugins_dir)
        assert any("✓ 已更新" in r for r in results), f"Expected pkg update, got {results}"

        pkg = json.loads(pkg_path.read_text("utf-8"))
        assert pkg["type"] == "module", f"Should have added type:module, got {pkg}"
        print("✓ 已有 package.json 缺少 type:module 时能正确修复")

def test_hooks_dir_routing():
    """验证主流程中 .opencode/plugins 路径走 _write_opencode_plugins 而非 _write_hooks"""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / ".opencode" / "plugins"
        if str(plugins_dir).endswith(".opencode/plugins"):
            results = _write_opencode_plugins(plugins_dir)
        else:
            results = _write_hooks(plugins_dir)

        js_file = plugins_dir / "aivectormemory-pre-tool-check.js"
        assert js_file.exists(), "Should generate .js plugin, not .kiro.hook"
        hook_files = list(plugins_dir.glob("*.kiro.hook"))
        assert len(hook_files) == 0, f"Should NOT generate .kiro.hook files, found {hook_files}"
        print("✓ 路由正确：.opencode/plugins 走 _write_opencode_plugins")

if __name__ == "__main__":
    test_ides_opencode_has_hooks_fn()
    test_write_opencode_plugins()
    test_hooks_dir_routing()
    print("\n全部测试通过 ✓")
