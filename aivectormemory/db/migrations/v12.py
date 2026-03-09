"""v12: user_memories 增加 username 列，实现 user scope 多用户隔离"""

from __future__ import annotations


def _has_column(conn, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    for row in rows:
        name = row["name"] if isinstance(row, dict) else row[1]
        if name == column:
            return True
    return False


def upgrade(conn, **_):
    if not _has_column(conn, "user_memories", "username"):
        conn.execute("ALTER TABLE user_memories ADD COLUMN username TEXT NOT NULL DEFAULT ''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_memories_username ON user_memories(username)")
