"""B1.5 自测：TaskRepo batch_create 去重 + update + list 过滤"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import tempfile
import sqlite_vec

from aivectormemory.db.schema import init_db
from aivectormemory.db.task_repo import TaskRepo


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


def test_batch_create_and_dedup():
    conn, db_path = setup_db()
    try:
        repo = TaskRepo(conn, "/test")
        tasks = [
            {"title": "任务A", "sort_order": 1},
            {"title": "任务B", "sort_order": 2},
            {"title": "任务A", "sort_order": 3},
        ]
        result = repo.batch_create("feat-1", tasks)
        assert result["created"] == 2
        assert result["skipped"] == 1
        result2 = repo.batch_create("feat-1", tasks)
        assert result2["created"] == 0
        assert result2["skipped"] == 3
        print("PASS: batch_create and dedup")
    finally:
        conn.close()
        os.unlink(db_path)


def test_batch_create_skip_empty_title():
    conn, db_path = setup_db()
    try:
        repo = TaskRepo(conn, "/test")
        result = repo.batch_create("feat-1", [{"title": ""}, {"title": "  "}])
        assert result["created"] == 0
        assert result["skipped"] == 2
        print("PASS: skip empty title")
    finally:
        conn.close()
        os.unlink(db_path)


def test_update():
    conn, db_path = setup_db()
    try:
        repo = TaskRepo(conn, "/test")
        repo.batch_create("feat-1", [{"title": "任务X", "sort_order": 0}])
        rows = repo.list_by_feature("feat-1")
        task_id = rows[0]["id"]
        updated = repo.update(task_id, status="completed")
        assert updated["status"] == "completed"
        updated2 = repo.update(task_id, title="任务X-改")
        assert updated2["title"] == "任务X-改"
        assert repo.update(9999, status="completed") is None
        print("PASS: update")
    finally:
        conn.close()
        os.unlink(db_path)


def test_list_by_feature_filter():
    conn, db_path = setup_db()
    try:
        repo = TaskRepo(conn, "/test")
        repo.batch_create("feat-1", [{"title": "A1", "sort_order": 1}, {"title": "A2", "sort_order": 2}])
        repo.batch_create("feat-2", [{"title": "B1", "sort_order": 1}])
        assert len(repo.list_by_feature("feat-1")) == 2
        assert len(repo.list_by_feature("feat-2")) == 1
        assert len(repo.list_by_feature()) == 3
        rows = repo.list_by_feature("feat-1")
        repo.update(rows[0]["id"], status="completed")
        assert len(repo.list_by_feature("feat-1", status="completed")) == 1
        assert len(repo.list_by_feature("feat-1", status="pending")) == 1
        print("PASS: list_by_feature filter")
    finally:
        conn.close()
        os.unlink(db_path)


def test_project_isolation():
    conn, db_path = setup_db()
    try:
        repo1 = TaskRepo(conn, "/proj1")
        repo2 = TaskRepo(conn, "/proj2")
        repo1.batch_create("feat-1", [{"title": "T1"}])
        repo2.batch_create("feat-1", [{"title": "T1"}])
        assert len(repo1.list_by_feature()) == 1
        assert len(repo2.list_by_feature()) == 1
        print("PASS: project isolation")
    finally:
        conn.close()
        os.unlink(db_path)


def test_batch_create_with_children():
    conn, db_path = setup_db()
    try:
        repo = TaskRepo(conn, "/test")
        result = repo.batch_create("issue/1", [
            {"title": "排查问题", "sort_order": 1, "children": [
                {"title": "查看日志", "sort_order": 1},
                {"title": "定位代码", "sort_order": 2},
            ]},
            {"title": "修复代码", "sort_order": 2, "children": [
                {"title": "修改文件", "sort_order": 1},
            ]},
        ], task_type="system")
        assert result["created"] == 5
        assert result["skipped"] == 0
        # 验证 task_type 写入
        rows = conn.execute("SELECT task_type FROM tasks WHERE project_dir='/test'").fetchall()
        assert all(r["task_type"] == "system" for r in rows)
        # 验证 parent_id 关系
        nodes = conn.execute("SELECT * FROM tasks WHERE project_dir='/test' AND parent_id=0 ORDER BY sort_order").fetchall()
        assert len(nodes) == 2
        kids = conn.execute("SELECT * FROM tasks WHERE project_dir='/test' AND parent_id=?", (nodes[0]["id"],)).fetchall()
        assert len(kids) == 2
        print("PASS: batch_create with children")
    finally:
        conn.close()
        os.unlink(db_path)


def test_list_tree_structure():
    conn, db_path = setup_db()
    try:
        repo = TaskRepo(conn, "/test")
        repo.batch_create("feat-1", [
            {"title": "节点A", "sort_order": 1, "children": [
                {"title": "子任务1", "sort_order": 1},
                {"title": "子任务2", "sort_order": 2},
            ]},
        ])
        tree = repo.list_by_feature("feat-1")
        assert len(tree) == 1
        assert tree[0]["title"] == "节点A"
        assert len(tree[0]["children"]) == 2
        assert tree[0]["children"][0]["title"] == "子任务1"
        # 节点状态应为 pending（所有子任务都是 pending）
        assert tree[0]["status"] == "pending"
        print("PASS: list tree structure")
    finally:
        conn.close()
        os.unlink(db_path)


def test_compute_status():
    conn, db_path = setup_db()
    try:
        repo = TaskRepo(conn, "/test")
        repo.batch_create("feat-1", [
            {"title": "节点", "sort_order": 1, "children": [
                {"title": "步骤1", "sort_order": 1},
                {"title": "步骤2", "sort_order": 2},
                {"title": "步骤3", "sort_order": 3},
            ]},
        ])
        tree = repo.list_by_feature("feat-1")
        kids = tree[0]["children"]
        # 完成一个子任务 → 节点 in_progress
        repo.update(kids[0]["id"], status="completed")
        tree = repo.list_by_feature("feat-1")
        assert tree[0]["status"] == "in_progress"
        # 全部完成 → 节点 completed
        repo.update(kids[1]["id"], status="completed")
        repo.update(kids[2]["id"], status="completed")
        tree = repo.list_by_feature("feat-1")
        assert tree[0]["status"] == "completed"
        print("PASS: compute status")
    finally:
        conn.close()
        os.unlink(db_path)


def test_complete_by_feature():
    conn, db_path = setup_db()
    try:
        repo = TaskRepo(conn, "/test")
        repo.batch_create("issue/99", [
            {"title": "步骤1", "sort_order": 1},
            {"title": "步骤2", "sort_order": 2},
        ])
        repo.update(repo.list_by_feature("issue/99")[0]["id"], status="in_progress")
        repo.complete_by_feature("issue/99")
        tasks = repo.list_by_feature("issue/99")
        assert all(t["status"] == "completed" for t in tasks)
        print("PASS: complete_by_feature")
    finally:
        conn.close()
        os.unlink(db_path)


def test_children_dedup_with_parent_id():
    """不同节点下相同标题的子任务不应被去重"""
    conn, db_path = setup_db()
    try:
        repo = TaskRepo(conn, "/test")
        repo.batch_create("feat-1", [
            {"title": "节点A", "sort_order": 1, "children": [
                {"title": "运行测试", "sort_order": 1},
            ]},
            {"title": "节点B", "sort_order": 2, "children": [
                {"title": "运行测试", "sort_order": 1},
            ]},
        ])
        # 两个"运行测试"应该都创建成功（parent_id 不同）
        rows = conn.execute("SELECT * FROM tasks WHERE project_dir='/test' AND title='运行测试'").fetchall()
        assert len(rows) == 2
        assert rows[0]["parent_id"] != rows[1]["parent_id"]
        print("PASS: children dedup with parent_id")
    finally:
        conn.close()
        os.unlink(db_path)


if __name__ == "__main__":
    test_batch_create_and_dedup()
    test_batch_create_skip_empty_title()
    test_update()
    test_list_by_feature_filter()
    test_project_isolation()
    test_batch_create_with_children()
    test_list_tree_structure()
    test_compute_status()
    test_complete_by_feature()
    test_children_dedup_with_parent_id()
    print("\nAll task_repo tests passed!")
