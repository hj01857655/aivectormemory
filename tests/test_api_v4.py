"""A4.5 自测：验证 API 层新字段读写"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import tempfile
import sqlite_vec

from aivectormemory.db.schema import init_db
from aivectormemory.db.issue_repo import IssueRepo


def setup():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    init_db(conn)
    return conn, db_path


def test_get_issues_includes_new_fields():
    conn, db_path = setup()
    try:
        repo = IssueRepo(conn, "/test")
        result = repo.create("2026-02-19", "test", parent_id=5)
        repo.update(result["id"], description="desc", feature_id="feat-1")
        issues, _ = repo.list_by_date(brief=False)
        assert len(issues) == 1
        issue = issues[0]
        assert issue["parent_id"] == 5
        assert issue["description"] == "desc"
        assert issue["feature_id"] == "feat-1"
        assert "investigation" in issue
        assert "root_cause" in issue
        assert "files_changed" in issue
        print("PASS: get_issues includes new fields")
    finally:
        conn.close()
        os.unlink(db_path)


def test_put_issue_updates_structured_fields():
    conn, db_path = setup()
    try:
        repo = IssueRepo(conn, "/test")
        result = repo.create("2026-02-19", "test")
        updated = repo.update(result["id"],
            description="new desc", investigation="step1",
            root_cause="bug", solution="fix it",
            files_changed='[{"path":"b.py","done":false}]',
            test_result="ok", notes="careful", feature_id="feat-2"
        )
        assert updated["description"] == "new desc"
        assert updated["investigation"] == "step1"
        assert updated["root_cause"] == "bug"
        assert updated["solution"] == "fix it"
        assert updated["files_changed"] == '[{"path":"b.py","done":false}]'
        assert updated["test_result"] == "ok"
        assert updated["notes"] == "careful"
        assert updated["feature_id"] == "feat-2"
        print("PASS: put_issue updates structured fields")
    finally:
        conn.close()
        os.unlink(db_path)


def test_post_issue_with_parent_id():
    conn, db_path = setup()
    try:
        repo = IssueRepo(conn, "/test")
        result = repo.create("2026-02-19", "parent issue")
        child = repo.create("2026-02-19", "child issue", parent_id=result["id"])
        row = conn.execute("SELECT parent_id FROM issues WHERE id=?", (child["id"],)).fetchone()
        assert row["parent_id"] == result["id"]
        print("PASS: post_issue with parent_id")
    finally:
        conn.close()
        os.unlink(db_path)


def test_delete_issue_compatible():
    conn, db_path = setup()
    try:
        repo = IssueRepo(conn, "/test")
        result = repo.create("2026-02-19", "to delete")
        deleted = repo.delete(result["id"])
        assert deleted["deleted"] is True
        assert conn.execute("SELECT * FROM issues WHERE id=?", (result["id"],)).fetchone() is None
        print("PASS: delete_issue compatible")
    finally:
        conn.close()
        os.unlink(db_path)


if __name__ == "__main__":
    test_get_issues_includes_new_fields()
    test_put_issue_updates_structured_fields()
    test_post_issue_with_parent_id()
    test_delete_issue_compatible()
    print("\nAll A4 API tests passed!")
