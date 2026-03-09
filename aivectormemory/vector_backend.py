import os
from functools import lru_cache

from aivectormemory.log import log

SUPPORTED_BACKENDS = {"sqlite", "qdrant"}
DEFAULT_BACKEND = "sqlite"
QDRANT_TABLE_COLLECTION_MAP = {
    "vec_memories": "aivm_memories",
    "vec_user_memories": "aivm_user_memories",
    "vec_issues_archive": "aivm_issues_archive",
}


def get_vector_backend() -> str:
    backend = (os.getenv("AIVM_VECTOR_BACKEND", DEFAULT_BACKEND) or "").strip().lower()
    if backend not in SUPPORTED_BACKENDS:
        log.warning("Unknown AIVM_VECTOR_BACKEND=%s, fallback to %s", backend, DEFAULT_BACKEND)
        return DEFAULT_BACKEND
    return backend


def _collection_name(vec_table: str) -> str:
    env_key = f"AIVM_QDRANT_COLLECTION_{vec_table.upper()}"
    return (os.getenv(env_key, "") or "").strip() or QDRANT_TABLE_COLLECTION_MAP.get(vec_table, vec_table)


@lru_cache(maxsize=1)
def _qdrant_client():
    if get_vector_backend() != "qdrant":
        return None
    try:
        from qdrant_client import QdrantClient
    except Exception as e:
        log.warning("Qdrant backend enabled but qdrant-client is unavailable: %s", e)
        return None
    url = (os.getenv("AIVM_QDRANT_URL", "http://127.0.0.1:6333") or "").strip()
    api_key = (os.getenv("AIVM_QDRANT_API_KEY", "") or "").strip() or None
    timeout = float(os.getenv("AIVM_QDRANT_TIMEOUT", "5"))
    return QdrantClient(url=url, api_key=api_key, timeout=timeout)


@lru_cache(maxsize=16)
def _ensure_collection(vec_table: str, dim: int):
    client = _qdrant_client()
    if client is None:
        return False
    try:
        from qdrant_client.http import models as qmodels
        name = _collection_name(vec_table)
        exists = False
        if hasattr(client, "collection_exists"):
            exists = bool(client.collection_exists(name))
        else:
            try:
                client.get_collection(name)
                exists = True
            except Exception:
                exists = False
        if not exists:
            client.create_collection(
                collection_name=name,
                vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
            )
        return True
    except Exception as e:
        log.warning("Qdrant ensure collection failed for %s: %s", vec_table, e)
        return False


def search_vectors(vec_table: str, embedding: list[float], limit: int) -> list[dict] | None:
    client = _qdrant_client()
    if client is None:
        return None
    if not _ensure_collection(vec_table, len(embedding)):
        return None
    try:
        name = _collection_name(vec_table)
        hits = client.search(
            collection_name=name,
            query_vector=embedding,
            limit=limit,
            with_payload=False,
            with_vectors=False,
        )
        rows = []
        for hit in hits:
            score = float(getattr(hit, "score", 0.0))
            # qdrant cosine score 越大越相似；仓库内部统一按 distance 升序处理。
            rows.append({"id": str(hit.id), "distance": max(0.0, 1.0 - score), "_backend": "qdrant"})
        return rows
    except Exception as e:
        log.warning("Qdrant search failed for %s: %s", vec_table, e)
        return None


def upsert_vector(vec_table: str, point_id: str, embedding: list[float]) -> bool:
    client = _qdrant_client()
    if client is None:
        return False
    if not _ensure_collection(vec_table, len(embedding)):
        return False
    try:
        from qdrant_client.http import models as qmodels
        name = _collection_name(vec_table)
        client.upsert(
            collection_name=name,
            points=[qmodels.PointStruct(id=str(point_id), vector=embedding, payload={})],
            wait=False,
        )
        return True
    except Exception as e:
        log.warning("Qdrant upsert failed for %s:%s (%s)", vec_table, point_id, e)
        return False


def delete_vector(vec_table: str, point_id: str) -> bool:
    client = _qdrant_client()
    if client is None:
        return False
    try:
        from qdrant_client.http import models as qmodels
        name = _collection_name(vec_table)
        client.delete(
            collection_name=name,
            points_selector=qmodels.PointIdsList(points=[str(point_id)]),
            wait=False,
        )
        return True
    except Exception as e:
        log.warning("Qdrant delete failed for %s:%s (%s)", vec_table, point_id, e)
        return False


def count_vectors(vec_table: str) -> int | None:
    client = _qdrant_client()
    if client is None:
        return None
    try:
        name = _collection_name(vec_table)
        if hasattr(client, "count"):
            r = client.count(collection_name=name, exact=True)
            return int(getattr(r, "count", 0))
    except Exception as e:
        log.warning("Qdrant count failed for %s (%s)", vec_table, e)
    return None


def health() -> dict:
    backend = get_vector_backend()
    out = {"backend": backend, "qdrant_available": False}
    if backend != "qdrant":
        return out
    client = _qdrant_client()
    if client is None:
        return out
    try:
        if hasattr(client, "get_collections"):
            client.get_collections()
        out["qdrant_available"] = True
    except Exception as e:
        out["error"] = str(e)
    return out
