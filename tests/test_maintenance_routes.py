import os
import sqlite3
from pathlib import Path

from aivectormemory.web.routes import maintenance


class _CM:
    def __init__(self, conn: sqlite3.Connection, db_path: str):
        self.conn = conn
        self._db_path = db_path


def _new_cm(tmp_path: Path) -> _CM:
    db_path = tmp_path / "maintenance.db"
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE memories (id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE vec_memories (id TEXT PRIMARY KEY, embedding BLOB)")
    conn.execute("CREATE TABLE user_memories (id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE vec_user_memories (id TEXT PRIMARY KEY, embedding BLOB)")
    conn.execute("CREATE TABLE issues (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE issues_archive (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE tasks_archive (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE session_state (id INTEGER PRIMARY KEY)")
    conn.commit()
    db_path.write_bytes(b"1234567890")
    return _CM(conn, str(db_path))


def test_health_check_sqlite_backend(tmp_path: Path, monkeypatch):
    cm = _new_cm(tmp_path)
    monkeypatch.setattr(maintenance.vector_backend, "health", lambda: {"backend": "sqlite", "qdrant_available": False})
    monkeypatch.setattr(maintenance.vector_backend, "count_vectors", lambda table: 0)

    out = maintenance.health_check(cm)

    assert out["vector_backend"] == "sqlite"
    assert out["qdrant_available"] is False
    assert "qdrant_vec_memories_total" not in out


def test_health_check_qdrant_backend_includes_counts(tmp_path: Path, monkeypatch):
    cm = _new_cm(tmp_path)
    monkeypatch.setattr(maintenance.vector_backend, "health", lambda: {"backend": "qdrant", "qdrant_available": True})
    monkeypatch.setattr(
        maintenance.vector_backend,
        "count_vectors",
        lambda table: {"vec_memories": 7, "vec_user_memories": 3}.get(table),
    )

    out = maintenance.health_check(cm)

    assert out["vector_backend"] == "qdrant"
    assert out["qdrant_available"] is True
    assert out["qdrant_vec_memories_total"] == 7
    assert out["qdrant_vec_user_memories_total"] == 3


def test_db_stats_qdrant_counts(tmp_path: Path, monkeypatch):
    cm = _new_cm(tmp_path)
    monkeypatch.setattr(maintenance.vector_backend, "health", lambda: {"backend": "qdrant", "qdrant_available": True})
    monkeypatch.setattr(
        maintenance.vector_backend,
        "count_vectors",
        lambda table: {"vec_memories": 9, "vec_user_memories": 4, "vec_issues_archive": 2}.get(table),
    )

    out = maintenance.db_stats(cm)

    assert out["vector_backend"] == "qdrant"
    assert out["qdrant_available"] is True
    assert out["qdrant_counts"]["vec_memories"] == 9
    assert out["qdrant_counts"]["vec_user_memories"] == 4
    assert out["qdrant_counts"]["vec_issues_archive"] == 2
    assert out["file_size_bytes"] == os.stat(cm._db_path).st_size
