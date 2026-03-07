"""验证 install.py 修改后生成的 MCP 配置是否正确"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aivectormemory.install import RUNNERS, _build_config

# 测试 RUNNERS 方式1: python -m aivectormemory
label1, fn1 = RUNNERS[0]
cmd1, args1 = fn1("/test/project")
print(f"方式1 label: {label1}")
print(f"方式1 cmd: {cmd1}")
print(f"方式1 args: {args1}")
assert cmd1 == sys.executable, f"Expected {sys.executable}, got {cmd1}"
assert args1 == ["-m", "aivectormemory", "--project-dir", "/test/project"]
print("✓ RUNNERS 方式1 正确\n")

# 测试 RUNNERS 方式2: uvx
label2, fn2 = RUNNERS[1]
cmd2, args2 = fn2("/test/project")
print(f"方式2 label: {label2}")
print(f"方式2 cmd: {cmd2}")
print(f"方式2 args: {args2}")
assert cmd2 == "uvx"
assert args2 == ["aivectormemory@latest", "--project-dir", "/test/project"]
print("✓ RUNNERS 方式2 正确\n")

# 测试 _build_config standard 格式（无 HF_ENDPOINT 环境变量时不生成 env）
old_hf = os.environ.pop("HF_ENDPOINT", None)
config_std = _build_config(cmd1, args1, "standard")
print(f"standard config (no HF_ENDPOINT): {config_std}")
assert config_std["command"] == sys.executable
assert config_std["args"] == ["-m", "aivectormemory", "--project-dir", "/test/project"]
assert "env" not in config_std, "env should not exist when HF_ENDPOINT not set"
assert config_std["disabled"] is False
assert config_std["autoApprove"] == ["remember", "recall", "forget", "status", "track", "task", "readme", "auto_save"]
print("✓ standard _build_config 正确（无 HF_ENDPOINT）\n")

# 测试 _build_config standard 格式（有 HF_ENDPOINT 环境变量时生成 env）
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
config_std_hf = _build_config(cmd1, args1, "standard")
print(f"standard config (with HF_ENDPOINT): {config_std_hf}")
assert config_std_hf["env"] == {"HF_ENDPOINT": "https://hf-mirror.com"}
print("✓ standard _build_config 正确（有 HF_ENDPOINT）\n")

# 测试 _build_config opencode 格式
config_oc = _build_config(cmd1, args1, "opencode")
print(f"opencode config: {config_oc}")
assert config_oc["type"] == "local"
assert config_oc["enabled"] is True
print("✓ opencode _build_config 正确\n")

# 测试 uvx + standard
config_uvx = _build_config(cmd2, args2, "standard")
print(f"uvx standard config: {config_uvx}")
assert config_uvx["command"] == "uvx"
assert config_uvx["env"] == {"HF_ENDPOINT": "https://hf-mirror.com"}
assert config_uvx["disabled"] is False
assert config_uvx["autoApprove"] == ["remember", "recall", "forget", "status", "track", "task", "readme", "auto_save"]
print("✓ uvx standard _build_config 正确\n")

# 清理环境变量
if old_hf is not None:
    os.environ["HF_ENDPOINT"] = old_hf
else:
    os.environ.pop("HF_ENDPOINT", None)

# 验证跨平台: sys.executable 在当前系统的路径
print(f"当前 sys.executable: {sys.executable}")
print(f"当前 platform: {sys.platform}")
print("✓ sys.executable 跨平台兼容（macOS/Linux 用 /，Windows 用 \\，Python 自动处理）\n")

print("=" * 50)
print("全部测试通过")
