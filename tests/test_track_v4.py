"""A3.5 自测：MCP JSON-RPC 验证 create(parent_id)/delete/update(结构化字段)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import sqlite3
import tempfile
import sqlite_vec

from aivectormemory.db.schema import init_db
from aivectormemory.tools.track import handle_track
from aivectormemory.errors import NotFoundError


class FakeCM:
    def __init__(self, conn, project_dir="/test"):
        self.conn = conn
        self.project_dir = project_dir


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


def test_create_with_parent_id():
    conn, db_path = setup()
    try:
        cm = FakeCM(conn)
        result = json.loads(handle_track({"action": "create", "title": "child", "parent_id": 42}, cm=cm))
        assert result["success"]
        row = conn.execute("SELECT parent_id FROM issues WHERE id=?", (result["id"],)).fetchone()
        assert row["parent_id"] == 42
        print("PASS: create with parent_id")
    finally:
        conn.close()
        os.unlink(db_path)


def test_delete():
    conn, db_path = setup()
    try:
        cm = FakeCM(conn)
        created = json.loads(handle_track({"action": "create", "title": "to delete"}, cm=cm))
        issue_number = created["issue_number"]
        result = json.loads(handle_track({"action": "delete", "issue_id": issue_number}, cm=cm))
        assert result["success"]
        assert result["deleted"] is True
        row = conn.execute("SELECT * FROM issues WHERE issue_number=?", (issue_number,)).fetchone()
        assert row is None
        print("PASS: delete")
    finally:
        conn.close()
        os.unlink(db_path)


def test_update_structured_fields():
    conn, db_path = setup()
    try:
        cm = FakeCM(conn)
        created = json.loads(handle_track({"action": "create", "title": "structured"}, cm=cm))
        issue_number = created["issue_number"]
        result = json.loads(handle_track({
            "action": "update", "issue_id": issue_number,
            "description": "desc", "investigation": "inv",
            "root_cause": "rc", "solution": "sol",
            "files_changed": '[{"path":"a.py","done":true}]',
            "test_result": "pass", "notes": "note",
            "feature_id": "feat-1"
        }, cm=cm))
        assert result["success"]
        issue = result["issue"]
        assert issue["issue_number"] == issue_number
        assert issue["status"] == "pending"
        assert "updated_at" in issue
        # 验证完整字段通过 get_by_id
        from aivectormemory.db.issue_repo import IssueRepo
        full = IssueRepo(conn, "/test").get_by_number(issue_number)
        assert full["description"] == "desc"
        assert full["investigation"] == "inv"
        assert full["root_cause"] == "rc"
        assert full["solution"] == "sol"
        assert full["files_changed"] == '[{"path":"a.py","done":true}]'
        assert full["test_result"] == "pass"
        assert full["notes"] == "note"
        assert full["feature_id"] == "feat-1"
        print("PASS: update structured fields")
    finally:
        conn.close()
        os.unlink(db_path)


def test_delete_not_found():
    conn, db_path = setup()
    try:
        cm = FakeCM(conn)
        try:
            handle_track({"action": "delete", "issue_id": 99999}, cm=cm)
            assert False, "Should raise ValueError"
        except (ValueError, NotFoundError) as e:
            assert "not found" in str(e)
        print("PASS: delete not found")
    finally:
        conn.close()
        os.unlink(db_path)


if __name__ == "__main__":
    test_create_with_parent_id()
    test_delete()
    test_update_structured_fields()
    test_delete_not_found()
    print("\nAll A3 track tests passed!")
