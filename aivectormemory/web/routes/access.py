"""Project-level access control helpers for web dashboard users."""

from __future__ import annotations

from datetime import datetime


def normalize_project_dir(project_dir: str | None) -> str:
    return (project_dir or "").strip().replace("\\", "/")


def grant_project_access(conn, username: str, project_dir: str) -> None:
    user = (username or "").strip()
    pdir = normalize_project_dir(project_dir)
    if not user or not pdir:
        return
    now = datetime.now().astimezone().isoformat()
    conn.execute(
        """
        INSERT OR IGNORE INTO user_project_access (username, project_dir, created_at)
        VALUES (?, ?, ?)
        """,
        (user, pdir, now),
    )


def revoke_project_access(conn, project_dir: str) -> None:
    pdir = normalize_project_dir(project_dir)
    if not pdir:
        return
    conn.execute("DELETE FROM user_project_access WHERE project_dir = ?", (pdir,))


def list_project_access(conn, username: str) -> set[str]:
    user = (username or "").strip()
    if not user:
        return set()
    rows = conn.execute(
        "SELECT project_dir FROM user_project_access WHERE username = ?",
        (user,),
    ).fetchall()
    out: set[str] = set()
    for row in rows:
        raw = row["project_dir"] if isinstance(row, dict) else row[0]
        out.add(normalize_project_dir(raw))
    return out


def has_project_access(conn, username: str, project_dir: str) -> bool:
    pdir = normalize_project_dir(project_dir)
    if not pdir:
        return False
    allowed = list_project_access(conn, username)
    return pdir in allowed

