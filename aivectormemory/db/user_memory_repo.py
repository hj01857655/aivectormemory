import json

from .base import BaseMemoryRepo


class UserMemoryRepo(BaseMemoryRepo):
    """管理 user_memories + vec_user_memories 表（跨项目用户偏好）"""
    TABLE = "user_memories"
    VEC_TABLE = "vec_user_memories"
    TAG_TABLE = "user_memory_tags"

    def __init__(self, conn, username: str | None = None):
        super().__init__(conn, project_dir="")
        self.username = (username or "").strip()

    def _scope_clause(self, table_alias: str = "user_memories") -> tuple[str, list]:
        if not self.username:
            return " AND username=''", []
        return f" AND {table_alias}.username=?", [self.username]

    def _build_insert(self, mid, content, tags, source, session_id, now, extra):
        cols = "id, username, content, tags, source, session_id, created_at, updated_at"
        vals = [mid, self.username, content, json.dumps(tags, ensure_ascii=False), source, session_id, now, now]
        return cols, vals

    def _is_same_scope(self, mid: str) -> bool:
        row = self.conn.execute("SELECT username FROM user_memories WHERE id=?", (mid,)).fetchone()
        if not row:
            return False
        return (row["username"] or "") == self.username

    def _match_filters(self, mem: dict, filters: dict) -> bool:
        return (mem.get("username", "") or "") == self.username

    def list_by_tags(self, tags: list[str], limit: int = 100, source: str | None = None,
                     tags_mode: str = "all", **_) -> list[dict]:
        sql, params = "SELECT * FROM user_memories WHERE 1=1", []
        where, where_params = self._scope_clause("user_memories")
        sql += where
        params.extend(where_params)
        if source:
            sql += " AND source=?"
            params.append(source)
        if tags_mode == "any":
            sql += " AND (" + " OR ".join(
                ["id IN (SELECT memory_id FROM user_memory_tags WHERE tag=?)" for _ in tags]) + ")"
            params.extend(tags)
        else:
            for tag in tags:
                sql += " AND id IN (SELECT memory_id FROM user_memory_tags WHERE tag=?)"
                params.append(tag)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def get_all(self, limit: int = 100, offset: int = 0) -> list[dict]:
        where, params = self._scope_clause("user_memories")
        rows = self.conn.execute(
            f"SELECT * FROM user_memories WHERE 1=1 {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset]).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        where, params = self._scope_clause("user_memories")
        return self.conn.execute(f"SELECT COUNT(*) FROM user_memories WHERE 1=1 {where}", params).fetchone()[0]

    def get_tag_counts(self) -> dict[str, int]:
        where, params = self._scope_clause("um")
        rows = self.conn.execute(
            "SELECT umt.tag, COUNT(*) as cnt "
            "FROM user_memory_tags umt "
            "JOIN user_memories um ON um.id = umt.memory_id "
            f"WHERE 1=1 {where} "
            "GROUP BY umt.tag",
            params,
        ).fetchall()
        return {r["tag"]: r["cnt"] for r in rows}

    def get_ids_with_tag(self, tag: str) -> list[dict]:
        where, params = self._scope_clause("um")
        return [dict(r) for r in self.conn.execute(
            "SELECT um.id, um.tags FROM user_memories um "
            "JOIN user_memory_tags umt ON um.id = umt.memory_id "
            f"WHERE umt.tag=? {where}",
            [tag, *params]
        ).fetchall()]

    def get_by_id(self, mid: str) -> dict | None:
        where, params = self._scope_clause("user_memories")
        row = self.conn.execute(
            f"SELECT * FROM user_memories WHERE id=? {where}",
            [mid, *params],
        ).fetchone()
        return dict(row) if row else None

    def delete(self, mid: str) -> bool:
        where, params = self._scope_clause("user_memories")
        cur = self.conn.execute(
            f"DELETE FROM user_memories WHERE id=? {where}",
            [mid, *params],
        )
        if cur.rowcount > 0:
            self.conn.execute("DELETE FROM vec_user_memories WHERE id=?", (mid,))
            self.conn.execute("DELETE FROM user_memory_tags WHERE memory_id=?", (mid,))
            self._commit()
            return True
        return False
