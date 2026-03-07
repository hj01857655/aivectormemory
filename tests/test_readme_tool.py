"""C1.7 自测：readme 工具 generate/diff 验证"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aivectormemory.tools.readme import handle_readme


def test_generate_default():
    result = handle_readme({"action": "generate"}, None)
    assert "content" in result
    assert result["lang"] == "en"
    assert "supported_langs" in result
    assert len(result["supported_langs"]) == 6
    content = result["content"]
    assert "AIVectorMemory" in content
    assert "remember" in content
    assert "recall" in content
    assert "auto_save" in content
    assert "task" in content
    assert "readme" in content
    assert "track" in content
    print("PASS: generate default")


def test_generate_sections():
    result = handle_readme({"action": "generate", "sections": ["tools"]}, None)
    content = result["content"]
    assert "MCP Tools" in content
    assert "remember" in content
    print("PASS: generate sections=tools")


def test_generate_lang():
    result = handle_readme({"action": "generate", "lang": "ja"}, None)
    assert result["lang"] == "ja"
    assert "content" in result
    print("PASS: generate lang=ja")


def test_diff_en():
    result = handle_readme({"action": "diff", "lang": "en"}, None)
    assert result["status"] == "exists"
    assert "missing_tools" in result
    assert "version_match" in result
    assert "generated" in result
    print(f"PASS: diff en - missing_tools={result['missing_tools']}, version_match={result['version_match']}")


def test_diff_unsupported():
    result = handle_readme({"action": "diff", "lang": "ko"}, None)
    assert "error" in result
    print("PASS: diff unsupported lang")


def test_invalid_action():
    result = handle_readme({"action": "xxx"}, None)
    assert "error" in result
    print("PASS: invalid action")


if __name__ == "__main__":
    test_generate_default()
    test_generate_sections()
    test_generate_lang()
    test_diff_en()
    test_diff_unsupported()
    test_invalid_action()
    print("\nAll readme tool tests passed!")
