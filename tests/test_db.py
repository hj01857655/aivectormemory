"""数据层测试：建表、CRUD、WAL 模式、sqlite-vec 向量搜索"""
import json
import os
import tempfile
import pytest
from pathlib import Path

_tmpdir = tempfile.mkdtemp()
os.environ.setdefault("HOME", _tmpdir)

import aivectormemory.config as config
config.DB_DIR = Path(_tmpdir) / ".aivectormemory"

from aivectormemory.db.connection import ConnectionManager
from aivectormemory.db.schema import init_db
from aivectormemory.db.memory_repo import MemoryRepo
from aivectormemory.db.user_memory_repo import UserMemoryRepo
from aivectormemory.db.state_repo import StateRepo
from aivectormemory.db.issue_repo import IssueRepo


@pytest.fixture
def project_dir():
    return tempfile.mkdtemp()

@pytest.fixture
def cm(project_dir):
    mgr = ConnectionManager(project_dir=project_dir)
    init_db(mgr.conn)
    yield mgr
    mgr.close()


class TestConnection:
    def test_wal_mode(self, cm):
        mode = cm.conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_sqlite_vec_loaded(self, cm):
        row = cm.conn.execute("SELECT vec_version()").fetchone()
        assert row[0]

    def test_tables_created(self, cm):
        all_names = [r[0] for r in cm.conn.execute(
            "SELECT name FROM sqlite_master ORDER BY name"
        ).fetchall()]
        assert "memories" in all_names
        assert "session_state" in all_names
        assert "issues" in all_names
        assert "issues_archive" in all_names
        assert "vec_memories" in all_names

    def test_project_dir_stored(self, cm):
        assert cm.project_dir != ""


class TestMemoryRepo:
    def _fake_embedding(self, seed=1.0):
        import numpy as np
        rng = np.random.RandomState(int(seed * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tolist()

    def test_insert_and_get(self, cm):
        repo = MemoryRepo(cm.conn, cm.project_dir)
        emb = self._fake_embedding(1.0)
        result = repo.insert("测试记忆", ["tag1"], "project", 1, emb)
        assert result["action"] == "created"
        mid = result["id"]
        mem = repo.get_by_id(mid)
        assert mem["content"] == "测试记忆"
        assert mem["project_dir"] == cm.project_dir
        assert json.loads(mem["tags"]) == ["tag1"]

    def test_user_scope_via_user_memory_repo(self, cm):
        """用户级记忆现在通过 UserMemoryRepo 存储到 user_memories 表"""
        repo = UserMemoryRepo(cm.conn)
        emb = self._fake_embedding(1.5)
        result = repo.insert("全局记忆", ["global"], 1, emb)
        assert result["action"] == "created"
        mem = repo.get_by_id(result["id"])
        assert mem["content"] == "全局记忆"
        assert json.loads(mem["tags"]) == ["global"]

    def test_dedup(self, cm):
        repo = MemoryRepo(cm.conn, cm.project_dir)
        emb = self._fake_embedding(2.0)
        r1 = repo.insert("原始内容", ["a"], "project", 1, emb)
        assert r1["action"] == "created"
        r2 = repo.insert("更新内容", ["b"], "project", 2, emb)
        assert r2["action"] == "updated"
        assert r2["id"] == r1["id"]
        mem = repo.get_by_id(r1["id"])
        assert mem["content"] == "更新内容"

    def test_search_by_vector(self, cm):
        repo = MemoryRepo(cm.conn, cm.project_dir)
        emb1 = self._fake_embedding(3.0)
        emb2 = self._fake_embedding(4.0)
        repo.insert("记忆A", [], "project", 1, emb1)
        repo.insert("记忆B", [], "project", 1, emb2)
        results = repo.search_by_vector(emb1, top_k=2, scope="project", project_dir=cm.project_dir)
        assert len(results) >= 1
        assert results[0]["content"] == "记忆A"

    def test_delete(self, cm):
        repo = MemoryRepo(cm.conn, cm.project_dir)
        emb = self._fake_embedding(5.0)
        r = repo.insert("待删除", [], "project", 1, emb)
        assert repo.delete(r["id"])
        assert repo.get_by_id(r["id"]) is None

    def test_count(self, cm):
        repo = MemoryRepo(cm.conn, cm.project_dir)
        assert repo.count(project_dir=cm.project_dir) == 0
        repo.insert("x", [], "project", 1, self._fake_embedding(20.0))
        assert repo.count(project_dir=cm.project_dir) == 1
    def test_list_by_tags(self, cm):
        repo = MemoryRepo(cm.conn, cm.project_dir)
        repo.insert("Python 踩坑", ["踩坑", "Python"], "project", 1, self._fake_embedding(30.0))
        repo.insert("Go 踩坑", ["踩坑", "Go"], "project", 1, self._fake_embedding(31.0))
        repo.insert("项目路径", ["项目知识"], "project", 1, self._fake_embedding(32.0))
        # 单标签
        results = repo.list_by_tags(["踩坑"], scope="project", project_dir=cm.project_dir)
        assert len(results) == 2
        # 多标签 AND
        results = repo.list_by_tags(["踩坑", "Python"], scope="project", project_dir=cm.project_dir)
        assert len(results) == 1
        assert "Python" in results[0]["content"]
        # 不匹配
        results = repo.list_by_tags(["不存在"], scope="project", project_dir=cm.project_dir)
        assert len(results) == 0


class TestStateRepo:
    def test_upsert_create(self, cm):
        repo = StateRepo(cm.conn, cm.project_dir)
        state = repo.upsert(current_task="测试任务", is_blocked=True, block_reason="等待确认")
        assert state["current_task"] == "测试任务"
        assert state["is_blocked"] is True
        assert state["block_reason"] == "等待确认"

    def test_upsert_update(self, cm):
        repo = StateRepo(cm.conn, cm.project_dir)
        repo.upsert(current_task="任务1")
        state = repo.upsert(current_task="任务2")
        assert state["current_task"] == "任务2"

    def test_get_empty(self, cm):
        repo = StateRepo(cm.conn, cm.project_dir)
        assert repo.get() is None

    def test_json_arrays(self, cm):
        repo = StateRepo(cm.conn, cm.project_dir)
        repo.upsert(progress=["步骤1", "步骤2"], pending=["待办1"])
        state = repo.get()
        assert state["progress"] == ["步骤1", "步骤2"]
        assert state["pending"] == ["待办1"]

    def test_project_isolation(self, cm):
        repo1 = StateRepo(cm.conn, cm.project_dir)
        repo2 = StateRepo(cm.conn, "/other/project")
        repo1.upsert(current_task="项目1任务")
        repo2.upsert(current_task="项目2任务")
        assert repo1.get()["current_task"] == "项目1任务"
        assert repo2.get()["current_task"] == "项目2任务"


class TestIssueRepo:
    def test_create(self, cm):
        repo = IssueRepo(cm.conn, cm.project_dir)
        r = repo.create("2025-02-13", "测试问题")
        assert r["issue_number"] == 1
        issue = repo.get_by_id(r["id"])
        assert issue["title"] == "测试问题"
        assert issue["status"] == "pending"

    def test_auto_number(self, cm):
        repo = IssueRepo(cm.conn, cm.project_dir)
        r1 = repo.create("2025-02-13", "问题1")
        r2 = repo.create("2025-02-13", "问题2")
        assert r1["issue_number"] == 1
        assert r2["issue_number"] == 2
        r3 = repo.create("2025-02-14", "问题3")
        assert r3["issue_number"] == 3

    def test_update(self, cm):
        repo = IssueRepo(cm.conn, cm.project_dir)
        r = repo.create("2025-02-13", "原标题")
        updated = repo.update(r["id"], title="新标题", status="in_progress")
        assert updated["title"] == "新标题"
        assert updated["status"] == "in_progress"

    def test_archive(self, cm):
        repo = IssueRepo(cm.conn, cm.project_dir)
        r = repo.create("2025-02-13", "待归档")
        result = repo.archive(r["id"])
        assert result["issue_id"] == r["id"]
        assert "archived_at" in result
        assert repo.get_by_id(r["id"]) is None
        archived, _ = repo.list_archived()
        assert len(archived) == 1
        assert archived[0]["title"] == "待归档"

    def test_list_by_date(self, cm):
        repo = IssueRepo(cm.conn, cm.project_dir)
        repo.create("2025-02-13", "A")
        repo.create("2025-02-13", "B")
        repo.create("2025-02-14", "C")
        all_issues, _ = repo.list_by_date()
        assert len(all_issues) == 3
        by_date, _ = repo.list_by_date(date="2025-02-13")
        assert len(by_date) == 2
        by_status, _ = repo.list_by_date(status="pending")
        assert len(by_status) == 3

    def test_list_archived(self, cm):
        repo = IssueRepo(cm.conn, cm.project_dir)
        r1 = repo.create("2025-02-13", "问题1")
        r2 = repo.create("2025-02-14", "问题2")
        repo.archive(r1["id"])
        repo.archive(r2["id"])
        all_archived, _ = repo.list_archived()
        assert len(all_archived) == 2
        by_date, _ = repo.list_archived(date="2025-02-13")
        assert len(by_date) == 1

    def test_project_isolation(self, cm):
        repo1 = IssueRepo(cm.conn, cm.project_dir)
        repo2 = IssueRepo(cm.conn, "/other/project")
        repo1.create("2025-02-13", "项目1问题")
        repo2.create("2025-02-13", "项目2问题")
        issues1, _ = repo1.list_by_date()
        issues2, _ = repo2.list_by_date()
        assert len(issues1) == 1
        assert len(issues2) == 1
