"""v11: 新增 user_project_access 表并回填历史项目可见性"""

from __future__ import annotations

from datetime import datetime

from aivectormemory.db.schema import USER_PROJECT_ACCESS_TABLE


def upgrade(conn, **_):
    conn.execute(USER_PROJECT_ACCESS_TABLE)

    users = [r["username"] for r in conn.execute("SELECT username FROM users").fetchall()]
    if not users:
        return

    project_dirs: set[str] = set()
    for table in ("memories", "session_state", "issues", "issues_archive", "tasks", "tasks_archive"):
        rows = conn.execute(f"SELECT DISTINCT project_dir FROM {table} WHERE project_dir <> ''").fetchall()
        for row in rows:
            pdir = (row["project_dir"] or "").strip().replace("\\", "/")
            if pdir:
                project_dirs.add(pdir)

    if not project_dirs:
        return

    now = datetime.now().astimezone().isoformat()
    for username in users:
        for pdir in project_dirs:
            conn.execute(
                """
                INSERT OR IGNORE INTO user_project_access (username, project_dir, created_at)
                VALUES (?, ?, ?)
                """,
                (username, pdir, now),
            )

