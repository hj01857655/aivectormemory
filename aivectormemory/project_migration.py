from __future__ import annotations

import json
import re
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from aivectormemory.config import get_db_path


TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class MigrationReport:
    db_path: str
    source: str
    target: str
    dry_run: bool
    backup_path: str
    session_state_action: str
    tables: dict[str, dict[str, int]]


def _safe_table_name(name: str) -> str:
    if not TABLE_NAME_PATTERN.match(name):
        raise ValueError(f"invalid table name: {name}")
    return name


def _list_project_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    tables: list[str] = []
    for row in rows:
        name = row[0] if isinstance(row, tuple) else row["name"]
        if not isinstance(name, str):
            continue
        try:
            cols = conn.execute(f"PRAGMA table_info({_safe_table_name(name)})").fetchall()
        except sqlite3.OperationalError:
            # vec0 虚拟表在未加载扩展时会报错，直接跳过。
            continue
        col_names = []
        for col in cols:
            if isinstance(col, tuple):
                col_names.append(col[1])
            else:
                col_names.append(col["name"])
        if "project_dir" in col_names:
            tables.append(name)
    return tables


def _count_for_dirs(conn: sqlite3.Connection, table: str, source: str, target: str) -> dict[str, int]:
    safe = _safe_table_name(table)
    src = conn.execute(f"SELECT count(*) FROM {safe} WHERE project_dir=?", (source,)).fetchone()[0]
    dst = conn.execute(f"SELECT count(*) FROM {safe} WHERE project_dir=?", (target,)).fetchone()[0]
    return {"source": int(src), "target": int(dst)}


def _json_list(raw: str) -> list[Any]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return parsed
    return []


def _merge_unique_list_json(a_raw: str, b_raw: str) -> str:
    merged: list[Any] = []
    for item in _json_list(a_raw) + _json_list(b_raw):
        if item not in merged:
            merged.append(item)
    return json.dumps(merged, ensure_ascii=False)


def _session_state_columns(conn: sqlite3.Connection) -> set[str]:
    cols = conn.execute("PRAGMA table_info(session_state)").fetchall()
    names: set[str] = set()
    for col in cols:
        names.add(col[1] if isinstance(col, tuple) else col["name"])
    return names


def _migrate_session_state(conn: sqlite3.Connection, source: str, target: str) -> str:
    cols = _session_state_columns(conn)
    has_last_sid = "last_session_id" in cols
    src = conn.execute("SELECT * FROM session_state WHERE project_dir=?", (source,)).fetchone()
    dst = conn.execute("SELECT * FROM session_state WHERE project_dir=?", (target,)).fetchone()

    if not src:
        return "noop"
    if not dst:
        conn.execute("UPDATE session_state SET project_dir=? WHERE project_dir=?", (target, source))
        return "rename"

    src_id = src["id"] if isinstance(src, sqlite3.Row) else src[0]
    dst_id = dst["id"] if isinstance(dst, sqlite3.Row) else dst[0]

    merged_is_blocked = int(bool(dst["is_blocked"]) or bool(src["is_blocked"]))
    merged_block_reason = (dst["block_reason"] or "").strip() or (src["block_reason"] or "").strip()
    merged_next_step = (dst["next_step"] or "").strip() or (src["next_step"] or "").strip()
    merged_current_task = (dst["current_task"] or "").strip() or (src["current_task"] or "").strip()
    merged_progress = _merge_unique_list_json(dst["progress"], src["progress"])
    merged_recent_changes = _merge_unique_list_json(dst["recent_changes"], src["recent_changes"])
    merged_pending = _merge_unique_list_json(dst["pending"], src["pending"])
    merged_updated_at = max(str(dst["updated_at"] or ""), str(src["updated_at"] or ""))

    if has_last_sid:
        merged_last_sid = max(int(dst["last_session_id"] or 0), int(src["last_session_id"] or 0))
        conn.execute(
            """
            UPDATE session_state
            SET is_blocked=?, block_reason=?, next_step=?, current_task=?,
                progress=?, recent_changes=?, pending=?, updated_at=?, last_session_id=?
            WHERE id=?
            """,
            (
                merged_is_blocked,
                merged_block_reason,
                merged_next_step,
                merged_current_task,
                merged_progress,
                merged_recent_changes,
                merged_pending,
                merged_updated_at,
                merged_last_sid,
                dst_id,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE session_state
            SET is_blocked=?, block_reason=?, next_step=?, current_task=?,
                progress=?, recent_changes=?, pending=?, updated_at=?
            WHERE id=?
            """,
            (
                merged_is_blocked,
                merged_block_reason,
                merged_next_step,
                merged_current_task,
                merged_progress,
                merged_recent_changes,
                merged_pending,
                merged_updated_at,
                dst_id,
            ),
        )

    conn.execute("DELETE FROM session_state WHERE id=?", (src_id,))
    return "merge"


def migrate_project_records(
    conn: sqlite3.Connection,
    *,
    source: str,
    target: str,
    dry_run: bool = False,
) -> MigrationReport:
    tables = _list_project_tables(conn)
    before = {t: _count_for_dirs(conn, t, source, target) for t in tables}

    if dry_run:
        conn.execute("SAVEPOINT aivm_migrate_project")

    session_state_action = "noop"
    try:
        if "session_state" in tables:
            session_state_action = _migrate_session_state(conn, source, target)

        for table in tables:
            if table == "session_state":
                continue
            safe = _safe_table_name(table)
            conn.execute(f"UPDATE {safe} SET project_dir=? WHERE project_dir=?", (target, source))

        after = {t: _count_for_dirs(conn, t, source, target) for t in tables}

        if dry_run:
            conn.execute("ROLLBACK TO aivm_migrate_project")
            conn.execute("RELEASE aivm_migrate_project")
        else:
            conn.commit()
    except Exception:
        if dry_run:
            conn.execute("ROLLBACK TO aivm_migrate_project")
            conn.execute("RELEASE aivm_migrate_project")
        else:
            conn.rollback()
        raise

    return MigrationReport(
        db_path=str(get_db_path()),
        source=source,
        target=target,
        dry_run=dry_run,
        backup_path="",
        session_state_action=session_state_action,
        tables={
            table: {
                "before_source": before[table]["source"],
                "before_target": before[table]["target"],
                "after_source": after[table]["source"],
                "after_target": after[table]["target"],
            }
            for table in tables
        },
    )


def run_migrate_project(
    *,
    source_dir: str,
    target_dir: str,
    dry_run: bool = False,
    no_backup: bool = False,
    json_output: bool = False,
) -> int:
    source = str(Path(source_dir).resolve())
    target = str(Path(target_dir).resolve())

    if source == target:
        print("source 与 target 相同，无需迁移。")
        return 0

    db_path = get_db_path()
    if not db_path.exists():
        print(f"数据库不存在：{db_path}")
        return 1

    backup_path = ""
    if not dry_run and not no_backup:
        backup_path = str(db_path) + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(db_path, backup_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    report = migrate_project_records(conn, source=source, target=target, dry_run=dry_run)
    conn.close()
    report.backup_path = backup_path

    if json_output:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
        return 0

    print("AIVectorMemory Project Migration")
    print("=" * 34)
    print(f"db: {report.db_path}")
    print(f"from: {report.source}")
    print(f"to:   {report.target}")
    print(f"dry_run: {report.dry_run}")
    if report.backup_path:
        print(f"backup: {report.backup_path}")
    print(f"session_state: {report.session_state_action}")
    print("-" * 34)
    for table, counts in report.tables.items():
        print(
            f"{table}: "
            f"source {counts['before_source']} -> {counts['after_source']}, "
            f"target {counts['before_target']} -> {counts['after_target']}"
        )
    print("result: OK")
    return 0

