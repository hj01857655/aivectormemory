import json
import math

from aivectormemory.utils import now_iso, safe_table
from aivectormemory.db.memory_repo import MemoryRepo
from aivectormemory.db.user_memory_repo import UserMemoryRepo
from aivectormemory.web.routes.access import has_project_access, list_project_access, normalize_project_dir


EMBEDDING_DIM = 384


def _embedding_error(message: str) -> str:
    return f"invalid embedding: {message}"


def _normalize_embedding(embedding):
    if not isinstance(embedding, list):
        return None, _embedding_error(f"must be a list of {EMBEDDING_DIM} numbers")
    if len(embedding) != EMBEDDING_DIM:
        return None, _embedding_error(f"must contain {EMBEDDING_DIM} float values")
    normalized = []
    for value in embedding:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None, _embedding_error("contains non-numeric value")
        f = float(value)
        if not math.isfinite(f):
            return None, _embedding_error("contains non-finite value")
        normalized.append(f)
    return normalized, None


def _same_project(mem: dict, pdir: str) -> bool:
    return normalize_project_dir(mem.get("project_dir")) == normalize_project_dir(pdir)


def _accessible_project_memories(repo: MemoryRepo, pdir: str, username: str | None) -> list[dict]:
    if not username:
        return repo.get_all(limit=999999, offset=0)
    allowed_projects = list_project_access(repo.conn, username)
    rows = []
    for project in sorted(allowed_projects):
        rows.extend(repo.get_all(limit=999999, offset=0, project_dir=project))
    rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return rows


def _user_repo(conn, username: str | None) -> UserMemoryRepo:
    return UserMemoryRepo(conn, username=username)


def get_memories(cm, params, pdir, username: str | None = None):
    scope = params.get("scope", ["all"])[0]
    query = params.get("query", [None])[0]
    tag = params.get("tag", [None])[0]
    source = params.get("source", [None])[0]
    exclude_tags = params.get("exclude_tags", [None])[0]
    limit = int(params.get("limit", [100])[0])
    offset = int(params.get("offset", [0])[0])

    repo = MemoryRepo(cm.conn, pdir)
    user_repo = _user_repo(cm.conn, username)

    if tag:
        if scope == "user":
            all_rows = user_repo.list_by_tags([tag], limit=9999, source=source)
        elif scope == "project":
            all_rows = repo.list_by_tags([tag], scope="project", project_dir=pdir, limit=9999, source=source)
        else:
            proj_rows = []
            for row in _accessible_project_memories(repo, pdir, username):
                row_tags = json.loads(row["tags"]) if isinstance(row["tags"], str) else (row.get("tags") or [])
                if tag in row_tags and (not source or row.get("source", "manual") == source):
                    proj_rows.append(row)
            user_rows = user_repo.list_by_tags([tag], limit=9999, source=source)
            all_rows = proj_rows + user_rows
        all_rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        if query:
            q = query.lower()
            all_rows = [r for r in all_rows if q in r.get("content", "").lower()]
        total = len(all_rows)
        results = all_rows[offset:offset + limit]
    elif exclude_tags:
        ex_set = set(exclude_tags.split(","))
        if scope == "user":
            all_rows = user_repo.get_all(limit=9999)
        elif scope == "project":
            all_rows = repo.get_all(limit=9999, offset=0, project_dir=pdir)
        else:
            all_rows = _accessible_project_memories(repo, pdir, username) + user_repo.get_all(limit=9999)
        all_rows = [r for r in all_rows if not ex_set.intersection(json.loads(r["tags"]) if isinstance(r["tags"], str) else (r["tags"] or []))]
        if source:
            all_rows = [r for r in all_rows if r.get("source", "manual") == source]
        if query:
            q = query.lower()
            all_rows = [r for r in all_rows if q in r.get("content", "").lower()]
        total = len(all_rows)
        results = all_rows[offset:offset + limit]
    else:
        if query:
            if scope == "user":
                all_rows = user_repo.get_all(limit=9999)
            elif scope == "project":
                all_rows = repo.get_all(limit=9999, offset=0, project_dir=pdir)
            else:
                all_rows = _accessible_project_memories(repo, pdir, username) + user_repo.get_all(limit=9999)
            if source:
                all_rows = [r for r in all_rows if r.get("source", "manual") == source]
            q = query.lower()
            all_rows = [r for r in all_rows if q in r.get("content", "").lower()]
            total = len(all_rows)
            results = all_rows[offset:offset + limit]
        else:
            if scope == "user":
                rows = user_repo.get_all(limit=limit, offset=offset)
                total = user_repo.count()
            elif scope == "project":
                rows = repo.get_all(limit=limit, offset=offset, project_dir=pdir)
                total = repo.count(project_dir=pdir)
            else:
                project_rows = _accessible_project_memories(repo, pdir, username)
                total = len(project_rows) + user_repo.count()
                rows = project_rows[offset:offset + limit]
                if len(rows) < limit:
                    user_offset = max(0, offset - len(project_rows))
                    user_rows = user_repo.get_all(limit=limit - len(rows), offset=user_offset)
                    rows = rows + user_rows
            if source:
                rows = [r for r in rows if r.get("source", "manual") == source]
            results = rows

    return {"memories": results, "total": total}


def get_memory_detail(cm, mid, pdir, username: str | None = None):
    repo = MemoryRepo(cm.conn, pdir)
    mem = repo.get_by_id(mid)
    if mem and _same_project(mem, pdir):
        return mem
    user_repo = _user_repo(cm.conn, username)
    mem = user_repo.get_by_id(mid)
    return mem or {"error": "not found"}


def put_memory(handler, cm, mid, pdir, username: str | None = None):
    from aivectormemory.web.api import _read_body
    body = _read_body(handler)
    repo = MemoryRepo(cm.conn, pdir)
    mem = repo.get_by_id(mid)
    if mem and not _same_project(mem, pdir):
        mem = None
    table = "memories"
    if not mem:
        user_repo = _user_repo(cm.conn, username)
        mem = user_repo.get_by_id(mid)
        table = "user_memories"
    if not mem:
        return {"error": "not found"}
    now = now_iso()
    updates = {}
    if "content" in body:
        updates["content"] = body["content"]
    if "tags" in body:
        updates["tags"] = json.dumps(body["tags"])
    if updates:
        updates["updated_at"] = now
        set_clause = ",".join(f"{k}=?" for k in updates)
        if table == "user_memories":
            current_username = (username or "").strip()
            cm.conn.execute(
                f"UPDATE {safe_table(table)} SET {set_clause} WHERE id=? AND username=?",
                [*updates.values(), mid, current_username],
            )
        else:
            cm.conn.execute(f"UPDATE {safe_table(table)} SET {set_clause} WHERE id=?", [*updates.values(), mid])
        cm.conn.commit()
    if table == "user_memories":
        return _user_repo(cm.conn, username).get_by_id(mid)
    return repo.get_by_id(mid)


def delete_memory(cm, mid, pdir, username: str | None = None):
    repo = MemoryRepo(cm.conn, pdir)
    mem = repo.get_by_id(mid)
    if mem and _same_project(mem, pdir):
        if repo.delete(mid):
            return {"deleted": True, "id": mid}
    user_repo = _user_repo(cm.conn, username)
    if user_repo.delete(mid):
        return {"deleted": True, "id": mid}
    return {"error": "not found"}


def delete_memories_batch(handler, cm, pdir, username: str | None = None):
    from aivectormemory.web.api import _read_body
    body = _read_body(handler)
    ids = body.get("ids", [])
    repo = MemoryRepo(cm.conn, pdir)
    user_repo = _user_repo(cm.conn, username)
    deleted = []
    for mid in ids:
        mem = repo.get_by_id(mid)
        if mem and _same_project(mem, pdir) and repo.delete(mid):
            deleted.append(mid)
        elif user_repo.delete(mid):
            deleted.append(mid)
    return {"deleted_count": len(deleted), "ids": deleted}


def export_memories(cm, params, pdir, username: str | None = None):
    scope = params.get("scope", ["all"])[0]
    repo = MemoryRepo(cm.conn, pdir)
    user_repo = _user_repo(cm.conn, username)

    if scope == "user":
        memories = user_repo.get_all(limit=999999)
        vec_table = "vec_user_memories"
    elif scope == "project":
        memories = repo.get_all(limit=999999, project_dir=pdir)
        vec_table = "vec_memories"
    else:
        memories = _accessible_project_memories(repo, pdir, username) + user_repo.get_all(limit=999999)
        vec_table = None

    result = []
    for m in memories:
        entry = dict(m)
        tbl = vec_table
        if tbl is None:
            tbl = "vec_user_memories" if user_repo.get_by_id(m["id"]) else "vec_memories"
        row = cm.conn.execute(f"SELECT embedding FROM {safe_table(tbl)} WHERE id=?", (m["id"],)).fetchone()
        if row:
            raw = row["embedding"]
            if isinstance(raw, (bytes, memoryview)):
                import struct
                if len(raw) >= 4 and len(raw) % 4 == 0:
                    entry["embedding"] = list(struct.unpack(f'{len(raw)//4}f', raw))
                else:
                    entry["embedding"] = None
            else:
                try:
                    entry["embedding"] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    entry["embedding"] = None
        else:
            entry["embedding"] = None
        result.append(entry)
    return {"memories": result, "count": len(result), "project_dir": pdir}


def import_memories(handler, cm, pdir, username: str | None = None):
    from aivectormemory.web.api import _read_body
    body = _read_body(handler)
    items = body.get("memories", [])
    if not isinstance(items, list) or not items:
        return {"error": "no memories to import"}
    repo = MemoryRepo(cm.conn, pdir)
    imported, skipped = 0, 0
    errors = []
    for idx, item in enumerate(items):
        try:
            if not isinstance(item, dict):
                skipped += 1
                errors.append({"index": idx, "error": "item must be an object"})
                continue

            mid = item.get("id", "")
            global_user_exists = cm.conn.execute("SELECT 1 FROM user_memories WHERE id=?", (mid,)).fetchone()
            if not mid or repo.get_by_id(mid) or global_user_exists:
                skipped += 1
                continue

            now = now_iso()
            tags = item.get("tags", "[]")
            if isinstance(tags, list):
                tags_str = json.dumps(tags, ensure_ascii=False)
            elif isinstance(tags, str):
                tags_str = tags
            else:
                tags_str = "[]"

            scope = item.get("scope", "project")
            if scope not in {"project", "user"}:
                skipped += 1
                errors.append({"id": mid, "error": "invalid scope"})
                continue

            target_project = normalize_project_dir(item.get("project_dir", pdir))
            if scope == "project":
                if not target_project:
                    skipped += 1
                    errors.append({"id": mid, "error": "project_dir required for project scope"})
                    continue
                if username and not has_project_access(cm.conn, username, target_project):
                    skipped += 1
                    errors.append({"id": mid, "error": "forbidden project_dir"})
                    continue
                if not username and target_project != normalize_project_dir(pdir):
                    skipped += 1
                    errors.append({"id": mid, "error": "forbidden project_dir"})
                    continue

            embedding = item.get("embedding")
            if embedding is None:
                from aivectormemory.embedding.engine import EmbeddingEngine
                embedding = EmbeddingEngine().encode(item.get("content", ""))
            embedding, emb_err = _normalize_embedding(embedding)
            if emb_err:
                skipped += 1
                errors.append({"id": mid, "error": emb_err})
                continue

            if scope == "user":
                cm.conn.execute(
                    "INSERT INTO user_memories (id, username, content, tags, source, session_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        mid,
                        (username or "").strip(),
                        item.get("content", ""),
                        tags_str,
                        item.get("source", "manual"),
                        item.get("session_id", 0),
                        item.get("created_at", now),
                        now,
                    ),
                )
                cm.conn.execute("INSERT INTO vec_user_memories (id, embedding) VALUES (?,?)", (mid, json.dumps(embedding)))
            else:
                cm.conn.execute(
                    "INSERT INTO memories (id, content, tags, scope, project_dir, session_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        mid,
                        item.get("content", ""),
                        tags_str,
                        scope,
                        target_project,
                        item.get("session_id", 0),
                        item.get("created_at", now),
                        now,
                    ),
                )
                cm.conn.execute("INSERT INTO vec_memories (id, embedding) VALUES (?,?)", (mid, json.dumps(embedding)))
            imported += 1
        except Exception as e:
            skipped += 1
            errors.append({"id": item.get("id", ""), "error": str(e)})
    cm.conn.commit()
    result = {"imported": imported, "skipped": skipped}
    if errors:
        result["errors"] = errors
    return result


def search_memories(handler, cm, pdir, username: str | None = None):
    from aivectormemory.web.api import _read_body
    body = _read_body(handler)
    query = body.get("query", "").strip()
    if not query:
        return {"error": "query required"}
    top_k = body.get("top_k", 20)
    scope = body.get("scope", "all")
    tags = body.get("tags", [])

    engine = getattr(cm, "_embedding_engine", None)
    if not engine:
        return {"error": "embedding engine not loaded"}

    embedding = engine.encode(query)
    repo = MemoryRepo(cm.conn, pdir)
    user_repo = _user_repo(cm.conn, username)

    if scope == "user":
        if tags:
            results = user_repo.search_by_vector_with_tags(embedding, tags, top_k=top_k)
        else:
            results = user_repo.search_by_vector(embedding, top_k=top_k)
    elif scope == "project":
        if tags:
            results = repo.search_by_vector_with_tags(embedding, tags, top_k=top_k, scope="project", project_dir=pdir)
        else:
            results = repo.search_by_vector(embedding, top_k=top_k, scope="project", project_dir=pdir)
    else:
        if tags:
            proj_results = repo.search_by_vector_with_tags(embedding, tags, top_k=top_k, scope="project", project_dir=pdir)
            user_results = user_repo.search_by_vector_with_tags(embedding, tags, top_k=top_k)
        else:
            proj_results = repo.search_by_vector(embedding, top_k=top_k, scope="project", project_dir=pdir)
            user_results = user_repo.search_by_vector(embedding, top_k=top_k)
        results = sorted(proj_results + user_results, key=lambda x: x.get("distance", 0))[:top_k]

    for r in results:
        r["similarity"] = round(1 - (r.get("distance", 0) ** 2) / 2, 4)
    return {"results": results, "count": len(results), "query": query}
