from typing import Dict, List, Optional
import hashlib
import uuid

from qdrant_client.http.models import Filter, FieldCondition, MatchValue, MatchText

from clients.qdrant_client import (
    search as qdrant_search,
    upsert_article,
    get_client,
    COLLECTION,
)
from embedding.provider import embed_texts


def _id_from_url(url: str) -> str:
    """ID determinista (UUID v5) para idempotencia por URL."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))

def index_one(doc: Dict):
    # forzamos URL a string para payload
    url_str = str(doc.get("url", ""))
    text = f"{doc.get('title', '')} {doc.get('content', '')}".strip()
    vec = embed_texts([text])[0].tolist()

    # Idempotencia entre corridas: mismo ID para misma URL
    vec_id: Optional[str] = _id_from_url(url_str) if url_str else None

    upsert_article(vec_id, vec, payload={**doc, "url": url_str})


def search_query(
    q: str,
    k: int = 10,
    title_contains: Optional[str] = None,
    source: Optional[str] = None,
) -> List[Dict]:
    """
    Búsqueda semántica (siempre) + filtros opcionales:
    - title_contains: full-text sobre 'title' (requiere índice de texto creado)
    - source: coincidencia exacta sobre 'source' (keyword index recomendado)
    """
    vec = embed_texts([q])[0].tolist()

    must = []
    if title_contains and title_contains.strip():
        must.append(FieldCondition(key="title", match=MatchText(text=title_contains.strip())))
    if source and source.strip():
        must.append(FieldCondition(key="source", match=MatchValue(value=source.strip())))

    query_filter: Optional[Filter] = Filter(must=must) if must else None

    hits = qdrant_search(vec, top_k=k, query_filter=query_filter)

    results: List[Dict] = []
    for h in hits:
        p = h.payload or {}
        results.append(
            {
                "title": p.get("title"),
                "url": p.get("url"),
                "source": p.get("source"),
                "score": float(h.score),
                "snippet": (p.get("content") or "")[:240],
                "published_at": p.get("published_at"),
            }
        )
    return results


def get_doc_by_url(url: str) -> Optional[Dict]:
    """
    Devuelve el payload completo del documento cuyo payload.url == url, o None si no existe.
    """
    client = get_client()
    flt = Filter(must=[FieldCondition(key="url", match=MatchValue(value=url))])
    points, _ = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=flt,
        with_payload=True,
        limit=1,
    )
    if not points:
        return None
    return points[0].payload
