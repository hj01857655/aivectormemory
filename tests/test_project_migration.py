import json
import sqlite3

from aivectormemory.project_migration import migrate_project_records


def _setup_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE session_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_dir TEXT NOT NULL UNIQUE,
            is_blocked INTEGER NOT NULL DEFAULT 0,
            block_reason TEXT NOT NULL DEFAULT '',
            next_step TEXT NOT NULL DEFAULT '',
            current_task TEXT NOT NULL DEFAULT '',
            progress TEXT NOT NULL DEFAULT '[]',
            recent_changes TEXT NOT NULL DEFAULT '[]',
            pending TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL,
            last_session_id INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute("CREATE TABLE memories (id TEXT PRIMARY KEY, project_dir TEXT NOT NULL, content TEXT)")
    conn.execute("CREATE TABLE issues (id INTEGER PRIMARY KEY AUTOINCREMENT, project_dir TEXT NOT NULL)")
    conn.execute("CREATE TABLE issues_archive (id INTEGER PRIMARY KEY AUTOINCREMENT, project_dir TEXT NOT NULL)")
    conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, project_dir TEXT NOT NULL)")
    conn.execute("CREATE TABLE tasks_archive (id INTEGER PRIMARY KEY AUTOINCREMENT, project_dir TEXT NOT NULL)")
    conn.commit()


def test_migrate_project_records_merge_session_state():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _setup_schema(conn)

    src = r"E:\VSCodeSpace\ace-lite"
    dst = r"E:\VSCodeSpace\ace"

    conn.execute(
        """
        INSERT INTO session_state
        (project_dir, is_blocked, block_reason, next_step, current_task, progress, recent_changes, pending, updated_at, last_session_id)
        VALUES (?, 1, 'src_reason', 'src_next', 'src_task', '["p1"]', '["r1"]', '["x1"]', '2026-03-09T10:00:00+08:00', 3)
        """,
        (src,),
    )
    conn.execute(
        """
        INSERT INTO session_state
        (project_dir, is_blocked, block_reason, next_step, current_task, progress, recent_changes, pending, updated_at, last_session_id)
        VALUES (?, 0, '', 'dst_next', '', '["p2"]', '["r2"]', '["x1","x2"]', '2026-03-09T11:00:00+08:00', 6)
        """,
        (dst,),
    )
    conn.execute("INSERT INTO memories (id, project_dir, content) VALUES ('m1', ?, 'hello')", (src,))
    conn.execute("INSERT INTO issues (project_dir) VALUES (?)", (src,))
    conn.commit()

    report = migrate_project_records(conn, source=src, target=dst, dry_run=False)
    assert report.session_state_action == "merge"

    src_cnt = conn.execute("SELECT count(*) FROM session_state WHERE project_dir=?", (src,)).fetchone()[0]
    dst_cnt = conn.execute("SELECT count(*) FROM session_state WHERE project_dir=?", (dst,)).fetchone()[0]
    assert src_cnt == 0
    assert dst_cnt == 1

    row = conn.execute("SELECT * FROM session_state WHERE project_dir=?", (dst,)).fetchone()
    assert row["is_blocked"] == 1
    assert row["block_reason"] == "src_reason"
    assert row["next_step"] == "dst_next"
    assert row["current_task"] == "src_task"
    assert row["last_session_id"] == 6
    assert row["updated_at"] == "2026-03-09T11:00:00+08:00"
    assert json.loads(row["progress"]) == ["p2", "p1"]
    assert json.loads(row["recent_changes"]) == ["r2", "r1"]
    assert json.loads(row["pending"]) == ["x1", "x2"]

    moved_mem = conn.execute("SELECT project_dir FROM memories WHERE id='m1'").fetchone()[0]
    assert moved_mem == dst
    moved_issue = conn.execute("SELECT count(*) FROM issues WHERE project_dir=?", (dst,)).fetchone()[0]
    assert moved_issue == 1


def test_migrate_project_records_dry_run_keeps_data():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _setup_schema(conn)

    src = r"E:\VSCodeSpace\ace-lite"
    dst = r"E:\VSCodeSpace\ace"
    conn.execute(
        """
        INSERT INTO session_state
        (project_dir, is_blocked, block_reason, next_step, current_task, progress, recent_changes, pending, updated_at, last_session_id)
        VALUES (?, 0, '', '', '', '[]', '[]', '[]', '2026-03-09T10:00:00+08:00', 1)
        """,
        (src,),
    )
    conn.execute("INSERT INTO memories (id, project_dir, content) VALUES ('m2', ?, 'hello')", (src,))
    conn.commit()

    report = migrate_project_records(conn, source=src, target=dst, dry_run=True)
    assert report.dry_run is True
    assert report.tables["session_state"]["after_source"] == 0
    assert report.tables["session_state"]["after_target"] == 1

    # dry-run 回滚后，源数据仍保留。
    src_state = conn.execute("SELECT count(*) FROM session_state WHERE project_dir=?", (src,)).fetchone()[0]
    src_mem = conn.execute("SELECT count(*) FROM memories WHERE project_dir=?", (src,)).fetchone()[0]
    dst_state = conn.execute("SELECT count(*) FROM session_state WHERE project_dir=?", (dst,)).fetchone()[0]
    assert src_state == 1
    assert src_mem == 1
    assert dst_state == 0

