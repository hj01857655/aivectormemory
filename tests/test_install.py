"""模拟干净环境安装 aivectormemory，检查依赖冲突"""
import subprocess, sys, tempfile, os

print(f"Python: {sys.version}")

# 创建临时虚拟环境
with tempfile.TemporaryDirectory() as tmpdir:
    venv_dir = os.path.join(tmpdir, "test_venv")
    print(f"\n1. 创建临时虚拟环境: {venv_dir}")
    subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
    
    pip = os.path.join(venv_dir, "bin", "pip")
    
    print("\n2. 尝试安装 aivectormemory（从 PyPI）...")
    result = subprocess.run(
        [pip, "install", "aivectormemory", "--dry-run", "-v"],
        capture_output=True, text=True, timeout=60
    )
    
    if result.returncode == 0:
        print("SUCCESS: 依赖解析通过")
        # 只打最后几行
        lines = result.stdout.strip().split("\n")
        for line in lines[-20:]:
            print(f"  {line}")
    else:
        print("FAILED: 依赖解析失败")
        print("stderr:", result.stderr[-2000:])
        print("stdout:", result.stdout[-2000:])
