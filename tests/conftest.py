"""pytest 全局 fixture：测试结束后自动清理 tmp 项目残留"""
import sqlite3
from pathlib import Path
import pytest

# 排除独立运行的检查脚本（含 sys.exit，会导致 pytest 收集崩溃）
collect_ignore = ["test_11_features.py"]


@pytest.fixture(autouse=True, scope="session")
def cleanup_tmp_projects_after_tests():
    yield
    db = Path.home() / ".aivectormemory" / "memory.db"
    if not db.exists():
        return
    conn = sqlite3.connect(str(db))
    for table in ("session_state", "issues", "issues_archive", "memories"):
        try:
            conn.execute(
                f"DELETE FROM {table} WHERE project_dir LIKE '/private/var/folders/%' OR project_dir LIKE '/tmp/%'"
            )
        except Exception:
            pass
    conn.commit()
    conn.close()
