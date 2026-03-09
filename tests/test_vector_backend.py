from pathlib import Path

import pytest

from aivectormemory import vector_backend
from aivectormemory.db import ConnectionManager, IssueRepo, MemoryRepo, init_db


@pytest.fixture(autouse=True)
def _clear_qdrant_caches():
    vector_backend._qdrant_client.cache_clear()
    vector_backend._ensure_collection.cache_clear()
    yield
    vector_backend._qdrant_client.cache_clear()
    vector_backend._ensure_collection.cache_clear()


def _new_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[ConnectionManager, MemoryRepo]:
    db_dir = tmp_path / "db"
    project_dir = tmp_path / "proj"
    project_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AIVM_DB_DIR", str(db_dir))
    monkeypatch.setenv("AIVM_DB_NAME", "memory.db")
    cm = ConnectionManager(project_dir=str(project_dir))
    init_db(cm.conn)
    return cm, MemoryRepo(cm.conn, cm.project_dir)


class _DummyEngine:
    def encode(self, text: str) -> list[float]:
        return [0.0] * 384


def test_vector_backend_defaults_to_sqlite(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("AIVM_VECTOR_BACKEND", raising=False)
    assert vector_backend.get_vector_backend() == "sqlite"


def test_vector_backend_invalid_value_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AIVM_VECTOR_BACKEND", "unknown-backend")
    assert vector_backend.get_vector_backend() == "sqlite"


def test_qdrant_mode_mirrors_upsert_and_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AIVM_VECTOR_BACKEND", "qdrant")
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(vector_backend, "search_vectors", lambda *args, **kwargs: [])

    def _fake_upsert(vec_table: str, point_id: str, embedding: list[float]) -> bool:
        calls.append(("upsert", vec_table))
        return True

    def _fake_delete(vec_table: str, point_id: str) -> bool:
        calls.append(("delete", vec_table))
        return True

    monkeypatch.setattr(vector_backend, "upsert_vector", _fake_upsert)
    monkeypatch.setattr(vector_backend, "delete_vector", _fake_delete)

    cm, repo = _new_repo(tmp_path, monkeypatch)
    mid = repo.insert("hello", ["qdrant"], "project", 1, [0.0] * 384)["id"]
    repo.delete(mid)
    cm.close()

    assert ("upsert", "vec_memories") in calls
    assert ("delete", "vec_memories") in calls


def test_qdrant_search_result_can_drive_vector_recall(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AIVM_VECTOR_BACKEND", "qdrant")
    monkeypatch.setattr(vector_backend, "upsert_vector", lambda *args, **kwargs: True)

    cm, repo = _new_repo(tmp_path, monkeypatch)
    mid = repo.insert("alpha memory", ["alpha"], "project", 1, [0.0] * 384)["id"]
    monkeypatch.setattr(
        vector_backend,
        "search_vectors",
        lambda *args, **kwargs: [{"id": mid, "distance": 0.01, "_backend": "qdrant"}],
    )

    rows = repo.search_by_vector([0.0] * 384, top_k=1, scope="project", project_dir=cm.project_dir)
    cm.close()

    assert len(rows) == 1
    assert rows[0]["id"] == mid


def test_qdrant_issue_archive_mirrors_upsert_and_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AIVM_VECTOR_BACKEND", "qdrant")
    calls: list[tuple[str, str]] = []

    def _fake_upsert(vec_table: str, point_id: str, embedding: list[float]) -> bool:
        calls.append(("upsert", vec_table))
        return True

    def _fake_delete(vec_table: str, point_id: str) -> bool:
        calls.append(("delete", vec_table))
        return True

    monkeypatch.setattr(vector_backend, "upsert_vector", _fake_upsert)
    monkeypatch.setattr(vector_backend, "delete_vector", _fake_delete)

    cm, _ = _new_repo(tmp_path, monkeypatch)
    repo = IssueRepo(cm.conn, cm.project_dir, engine=_DummyEngine())
    created = repo.create("2026-03-09", "qdrant issue", "test content")
    repo.archive(created["id"])

    row = cm.conn.execute("SELECT id FROM issues_archive ORDER BY id DESC LIMIT 1").fetchone()
    archive_id = int(row["id"])
    deleted = repo.delete_archived(archive_id)
    cm.close()

    assert deleted is not None
    assert ("upsert", "vec_issues_archive") in calls
    assert ("delete", "vec_issues_archive") in calls


def test_qdrant_issue_archive_search_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AIVM_VECTOR_BACKEND", "qdrant")
    monkeypatch.setattr(vector_backend, "upsert_vector", lambda *args, **kwargs: True)

    cm, _ = _new_repo(tmp_path, monkeypatch)
    repo = IssueRepo(cm.conn, cm.project_dir, engine=_DummyEngine())
    created = repo.create("2026-03-09", "archive search issue", "search target")
    repo.archive(created["id"])
    row = cm.conn.execute("SELECT id FROM issues_archive ORDER BY id DESC LIMIT 1").fetchone()
    archive_id = int(row["id"])

    monkeypatch.setattr(
        vector_backend,
        "search_vectors",
        lambda *args, **kwargs: [{"id": str(archive_id), "distance": 0.05, "_backend": "qdrant"}],
    )
    rows = repo.search_archive_by_vector([0.0] * 384, top_k=1)
    cm.close()

    assert len(rows) == 1
    assert rows[0]["id"] == archive_id
    assert rows[0]["similarity"] >= 0.9
