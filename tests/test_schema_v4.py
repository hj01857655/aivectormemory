"""A1.9 自测：删除测试数据库，运行 init_db 验证迁移无报错"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import tempfile
import sqlite_vec

from aivectormemory.db.schema import init_db, CURRENT_SCHEMA_VERSION


def test_fresh_init_db():
    """全新数据库初始化"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        init_db(conn)

        # 验证 schema version
        ver = conn.execute("SELECT version FROM schema_version").fetchone()["version"]
        assert ver == CURRENT_SCHEMA_VERSION, f"Expected version {CURRENT_SCHEMA_VERSION}, got {ver}"

        # 验证 memories 表 source 字段
        mem_cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
        assert "source" in mem_cols, "memories missing column: source"

        # 验证 issues 表新字段
        issue_cols = {row[1] for row in conn.execute("PRAGMA table_info(issues)").fetchall()}
        for col in ["description", "investigation", "root_cause", "solution",
                     "files_changed", "test_result", "notes", "feature_id", "parent_id"]:
            assert col in issue_cols, f"issues missing column: {col}"

        # 验证 issues_archive 表新字段
        archive_cols = {row[1] for row in conn.execute("PRAGMA table_info(issues_archive)").fetchall()}
        for col in ["description", "investigation", "root_cause", "solution",
                     "files_changed", "test_result", "notes", "feature_id", "parent_id", "status"]:
            assert col in archive_cols, f"issues_archive missing column: {col}"

        # 验证 tasks 表存在且字段正确（含 v6 新增字段）
        task_cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
        for col in ["id", "project_dir", "feature_id", "title", "status", "sort_order",
                     "parent_id", "task_type", "metadata", "created_at", "updated_at"]:
            assert col in task_cols, f"tasks missing column: {col}"

        # 验证索引
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(tasks)").fetchall()}
        for idx in ["idx_tasks_project", "idx_tasks_feature", "idx_tasks_status"]:
            assert idx in indexes, f"Missing index: {idx}"

        conn.close()
        print("PASS: fresh init_db")
    finally:
        os.unlink(db_path)


def test_migrate_from_v3():
    """从 v3 迁移到 v4"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)

        # 模拟 v3 数据库：手动建旧表
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL DEFAULT 0)")
        conn.execute("INSERT INTO schema_version (version) VALUES (3)")
        conn.execute("""CREATE TABLE issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_dir TEXT NOT NULL DEFAULT '',
            issue_number INTEGER NOT NULL,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            content TEXT NOT NULL DEFAULT '',
            memory_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE issues_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_dir TEXT NOT NULL DEFAULT '',
            issue_number INTEGER NOT NULL,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            memory_id TEXT NOT NULL DEFAULT '',
            archived_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        conn.commit()

        # 插入一条旧数据
        conn.execute(
            "INSERT INTO issues (project_dir, issue_number, date, title, content, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            ("/test", 1, "2026-02-19", "test issue", "old content", "2026-02-19", "2026-02-19")
        )
        conn.commit()

        # 运行迁移
        init_db(conn)

        # 验证版本
        ver = conn.execute("SELECT version FROM schema_version").fetchone()["version"]
        assert ver == CURRENT_SCHEMA_VERSION, f"Expected version {CURRENT_SCHEMA_VERSION}, got {ver}"

        # 验证旧数据保留
        row = conn.execute("SELECT * FROM issues WHERE issue_number=1").fetchone()
        assert row["content"] == "old content"
        assert row["description"] == ""
        assert row["parent_id"] == 0
        assert row["files_changed"] == "[]"

        # 验证 tasks 表存在且含 v6 新字段
        task_cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
        for col in ["feature_id", "parent_id", "task_type", "metadata"]:
            assert col in task_cols, f"tasks missing column: {col}"

        conn.close()
        print("PASS: migrate from v3")
    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    test_fresh_init_db()
    test_migrate_from_v3()
    print("\nAll A1 schema tests passed!")
