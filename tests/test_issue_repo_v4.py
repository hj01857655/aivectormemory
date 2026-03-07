"""A2.4 自测：验证 create/update/archive 的新字段读写正确"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import tempfile
import sqlite_vec

from aivectormemory.db.schema import init_db
from aivectormemory.db.issue_repo import IssueRepo


def setup_db():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    init_db(conn)
    return conn, db_path


def test_create_with_parent_id():
    conn, db_path = setup_db()
    try:
        repo = IssueRepo(conn, "/test")
        result = repo.create("2026-02-19", "child issue", parent_id=42)
        assert not result.get("deduplicated"), "Should not be deduplicated"
        row = conn.execute("SELECT * FROM issues WHERE id=?", (result["id"],)).fetchone()
        assert row["parent_id"] == 42, f"Expected parent_id=42, got {row['parent_id']}"
        assert row["description"] == "", f"Expected empty description, got {row['description']}"
        print("PASS: create with parent_id")
    finally:
        conn.close()
        os.unlink(db_path)


def test_update_structured_fields():
    conn, db_path = setup_db()
    try:
        repo = IssueRepo(conn, "/test")
        result = repo.create("2026-02-19", "test issue")
        issue_id = result["id"]

        updated = repo.update(issue_id,
            description="问题描述",
            investigation="排查步骤1\n排查步骤2",
            root_cause="根本原因",
            solution="解决方案",
            files_changed='[{"path":"a.py","done":true}]',
            test_result="测试通过",
            notes="注意事项",
            feature_id="v0.2.5-track"
        )
        assert updated["description"] == "问题描述"
        assert updated["investigation"] == "排查步骤1\n排查步骤2"
        assert updated["root_cause"] == "根本原因"
        assert updated["solution"] == "解决方案"
        assert updated["files_changed"] == '[{"path":"a.py","done":true}]'
        assert updated["test_result"] == "测试通过"
        assert updated["notes"] == "注意事项"
        assert updated["feature_id"] == "v0.2.5-track"
        print("PASS: update structured fields")
    finally:
        conn.close()
        os.unlink(db_path)


def test_archive_with_structured_fields():
    conn, db_path = setup_db()
    try:
        repo = IssueRepo(conn, "/test")
        result = repo.create("2026-02-19", "archive test", parent_id=10)
        issue_id = result["id"]

        repo.update(issue_id,
            description="desc", investigation="inv", root_cause="rc",
            solution="sol", files_changed='[]', test_result="pass",
            notes="note", feature_id="feat-1", status="completed"
        )

        archived = repo.archive(issue_id)
        assert archived["archived_at"]

        row = conn.execute("SELECT * FROM issues_archive WHERE issue_number=?",
                          (result["issue_number"],)).fetchone()
        assert row["description"] == "desc"
        assert row["investigation"] == "inv"
        assert row["root_cause"] == "rc"
        assert row["solution"] == "sol"
        assert row["test_result"] == "pass"
        assert row["notes"] == "note"
        assert row["feature_id"] == "feat-1"
        assert row["parent_id"] == 10
        assert row["status"] == "completed"

        assert conn.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone() is None
        print("PASS: archive with structured fields")
    finally:
        conn.close()
        os.unlink(db_path)


if __name__ == "__main__":
    test_create_with_parent_id()
    test_update_structured_fields()
    test_archive_with_structured_fields()
    print("\nAll A2 issue_repo tests passed!")
