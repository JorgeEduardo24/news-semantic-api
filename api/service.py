from typing import Dict, List, Optional, Any
import uuid
import datetime as dt
from collections import defaultdict, Counter

import numpy as np
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, MatchText

import clients.qdrant_client as qc
from embedding.provider import embed_texts, embed_batch

# Schemas de respuesta para los endpoints bonus
from .schemas import (
    StorylineResponse, StoryCluster, StoryItem,
    PerspectiveResponse, SourcePerspective,
    GraphResponse, GraphNode, GraphEdge
)

# Utilidades de análisis (clustering, NER, TF-IDF, heurística de tono)
from .analysis import (
    storyline_clusters, extract_entities, tfidf_top_terms, _sentiment_score
)


# -----------------------------------
# Utilidades internas
# -----------------------------------
def _id_from_url(url: str) -> str:
    """ID determinista (UUID v5) para idempotencia por URL."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))


def _maybe_parse_dt(value: Any) -> Optional[dt.datetime]:
    """Convierte cadenas ISO8601/fecha a datetime; devuelve None en fallos."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    if isinstance(value, str):
        # tolera 'YYYY-MM-DD' o ISO con hora
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            # último intento: sólo fecha
            try:
                return dt.datetime.strptime(value[:10], "%Y-%m-%d")
            except Exception:
                return None
    return None


def _filter_by_date(results: List[Dict], date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Dict]:
    """Filtra por published_at en el intervalo [date_from, date_to]."""
    if not date_from and not date_to:
        return results

    df = _maybe_parse_dt(date_from) if isinstance(date_from, str) else date_from
    dt_ = _maybe_parse_dt(date_to) if isinstance(date_to, str) else date_to

    out: List[Dict] = []
    for r in results:
        ts = _maybe_parse_dt(r.get("published_at"))
        if ts is None:
            # Si no hay fecha, por defecto lo dejamos pasar (o exclúyelo si prefieres)
            out.append(r)
            continue
        if df and ts < df:
            continue
        if dt_ and ts > dt_:
            continue
        out.append(r)
    return out


# -----------------------------------
# Ingesta / Indexación
# -----------------------------------
def index_one(doc: Dict):
    """
    Indexa un documento en Qdrant.
    - Embebe título+contenido
    - Usa ID determinista por URL (si existe) para idempotencia
    """
    url_str = str(doc.get("url", ""))
    text = f"{doc.get('title', '')} {doc.get('content', '')}".strip()
    vec = embed_texts([text])[0].tolist()

    # Idempotencia entre corridas: mismo ID para misma URL
    vec_id: Optional[str] = _id_from_url(url_str) if url_str else None

    qc.upsert_article(vec_id, vec, payload={**doc, "url": url_str})


# -----------------------------------
# Búsqueda base (existente)
# -----------------------------------
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

    hits = qc.search(vec, top_k=k, query_filter=query_filter)

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
                "content": p.get("content"),  # útil para análisis extra
            }
        )
    return results


def get_doc_by_url(url: str) -> Optional[Dict]:
    """
    Devuelve el payload completo del documento cuyo payload.url == url, o None si no existe.
    """
    client = qc.get_client()
    flt = Filter(must=[FieldCondition(key="url", match=MatchValue(value=url))])
    points, _ = client.scroll(
        collection_name=qc.COLLECTION,
        scroll_filter=flt,
        with_payload=True,
        limit=1,
    )
    if not points:
        return None
    return points[0].payload


# -----------------------------------
# Helpers para endpoints BONUS
# -----------------------------------
def get_topn_for_query(
    q: str,
    k: int = 20,
    title_contains: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Wrapper que reutiliza search_query y aplica filtros de fecha en memoria.
    Mantiene la firma simple para ser invocado desde los builders.
    """
    items = search_query(q=q, k=k, title_contains=title_contains, source=source)
    items = _filter_by_date(items, date_from=date_from, date_to=date_to)
    return items


# -----------------------------------
# Builders: /storyline, /analysis/perspective, /graph/entities
# -----------------------------------
def build_storyline(
    q: str,
    k: int = 20,
    title_contains: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> StorylineResponse:
    """
    Agrupa top-N resultados en “hilos” (clusters) por similitud (coseno) y los ordena temporalmente.
    """
    docs = get_topn_for_query(
        q, k=k, title_contains=title_contains, source=source, date_from=date_from, date_to=date_to
    )
    texts = [(d.get("title", "") or "") + "\n" + (d.get("content", "") or "") for d in docs]
    # embed_batch -> List[List[float]]
    emb = embed_batch(texts)

    # Fechas normalizadas
    dates: List[Optional[dt.datetime]] = []
    for d in docs:
        dates.append(_maybe_parse_dt(d.get("published_at")))

    clusters_idx = storyline_clusters(emb, [d.get("title", "") for d in docs], dates)
    clusters: List[StoryCluster] = []
    for cid, idxs in enumerate(clusters_idx):
        sub = [docs[i] for i in idxs]
        # título representativo: el primero del cluster
        rep = sub[0] if sub else {}
        # rango temporal del cluster
        dts = [ _maybe_parse_dt(s.get("published_at")) for s in sub if s.get("published_at") ]
        tmin = min(dts) if dts else None
        tmax = max(dts) if dts else None
        items = [
            StoryItem(
                title=s.get("title", "") or "",
                url=s.get("url"),
                source=s.get("source", "") or "",
                published_at=s.get("published_at"),
                score=s.get("score"),
            )
            for s in sub
        ]
        clusters.append(
            StoryCluster(
                cluster_id=cid,
                title=(rep.get("title", "") or ""),
                timespan=[tmin, tmax],
                items=items,
            )
        )
    return StorylineResponse(query=q, clusters=clusters)


def build_perspective(
    q: str,
    sources_filter: Optional[List[str]] = None,
    k: int = 40,
    title_contains: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> PerspectiveResponse:
    """
    Compara cobertura por fuente: entidades, términos (TF-IDF), tono heurístico, volumen e histograma temporal.
    """
    # Adaptamos filtro de fuentes: si hay varias, haremos filtrado en memoria después.
    docs = get_topn_for_query(
        q, k=k, title_contains=title_contains,
        # Pasamos source sólo si es una única fuente (optimization),
        source=(sources_filter[0] if sources_filter and len(sources_filter) == 1 else None),
        date_from=date_from, date_to=date_to
    )

    # Si se pidieron múltiples fuentes, filtramos en memoria
    if sources_filter and len(sources_filter) > 1:
        allowed = set(s.strip() for s in sources_filter)
        docs = [d for d in docs if (d.get("source") or "") in allowed]

    by_source: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for d in docs:
        by_source[d.get("source", "unknown")].append(d)

    res: List[SourcePerspective] = []
    for src, items in by_source.items():
        texts = [(i.get("title", "") or "") + "\n" + (i.get("content", "") or "") for i in items]
        ents = []
        sentiments = []
        dates = []
        for t, i in zip(texts, items):
            ents.extend(extract_entities(t))
            sentiments.append(_sentiment_score(t))
            # yyyy-mm-dd para histograma simple
            day = (i.get("published_at") or "")[:10]
            dates.append(day if len(day) == 10 else "unknown")
        top_entities = [e for e, _ in Counter([x[0] for x in ents]).most_common(8)]
        top_terms = tfidf_top_terms(texts, k=8)
        hist = Counter(dates)
        res.append(
            SourcePerspective(
                source=src,
                volume=len(items),
                top_entities=top_entities,
                avg_sentiment=float(np.mean(sentiments)) if sentiments else 0.0,
                top_terms=top_terms,
                time_histogram=dict(sorted(hist.items())),
            )
        )

    # Ordena por volumen descendente
    res_sorted = sorted(res, key=lambda s: s.volume, reverse=True)
    return PerspectiveResponse(query=q, sources=res_sorted)

def build_graph(
    q: str,
    k: int = 30,
    title_contains: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> GraphResponse:
    """
    Grafo de co-ocurrencia de entidades por artículo (nivel documento).
    Para granularidad por oración, se puede extender con segmentación de spaCy.
    """
    docs = get_topn_for_query(
        q, k=k, title_contains=title_contains, source=source, date_from=date_from, date_to=date_to
    )

    co = Counter()
    types: Dict[str, str] = {}
    for d in docs:
        text = (d.get("title", "") or "") + "\n" + (d.get("content", "") or "")
        ents = extract_entities(text)
        # normaliza claves por artículo y evita duplicados dentro del mismo doc
        uniq: Dict[str, str] = {}
        for label, t in ents:
            key = label.strip()
            if key:
                uniq[key] = t
        labels = sorted(uniq.keys())
        for a_i in range(len(labels)):
            for b_i in range(a_i + 1, len(labels)):
                a, b = labels[a_i], labels[b_i]
                co[(a, b)] += 1
        types.update(uniq)

    nodes = [GraphNode(id=k_, label=k_, type=types.get(k_, "MISC")) for k_ in sorted(types.keys())]
    edges = [GraphEdge(source=a, target=b, weight=w) for (a, b), w in co.most_common(200)]
    return GraphResponse(query=q, nodes=nodes, edges=edges)


