import os
from typing import List, Optional

from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from qdrant_client.http.models import TextIndexParams, PayloadSchemaType


QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION = os.getenv("QDRANT_COLLECTION", "news")

# Debe coincidir con embedding/provider.DIMS
VECTOR_SIZE = 384


def get_client() -> QdrantClient:
    # check_compatibility=False evita berrinches si servidor/cliente no son exactamente iguales
    return QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        timeout=30,
        https=False,
        prefer_grpc=False,
    )


def _ensure_payload_indices(c: QdrantClient) -> None:
    """
    Crea índices de payload (idempotente):
    - Full-text sobre 'title'
    - Keyword sobre 'source'
    """
    # Índice full-text en 'title'
    try:
        c.create_payload_index(
            collection_name=COLLECTION,
            field_name="title",
            field_schema=TextIndexParams(
                tokenizer="latin",   # usa "multilingual" si mezclas es/en/pt en serio
                min_token_len=2,
                max_token_len=24,
                lowercase=True,
            ),
        )
    except Exception:
        # ya existe o versión de servidor sin soporte -> ignoramos
        pass

    # Índice keyword en 'source' (útil para filtros por fuente)
    try:
        c.create_payload_index(
            collection_name=COLLECTION,
            field_name="source",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception:
        pass


def ensure_collection():
    c = get_client()
    try:
        cols = c.get_collections().collections or []
        names = [x.name for x in cols]
    except Exception:
        names = []

    if COLLECTION not in names:
        c.create_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(size=VECTOR_SIZE, distance=qm.Distance.COSINE),
            optimizers_config=qm.OptimizersConfigDiff(indexing_threshold=20000),
        )

    # Crear índices (sean nuevos o ya existentes), no falla si ya existen
    _ensure_payload_indices(c)


def upsert_article(vec_id: Optional[str], vector: List[float], payload: dict):
    c = get_client()
    # usa UUID si no te pasan un id (si quieres idempotencia por URL, genera el hash en service.index_one)
    pid = vec_id or str(uuid4())
    point = qm.PointStruct(id=pid, vector=vector, payload=payload)
    c.upsert(collection_name=COLLECTION, points=[point])


def search(
    vector: List[float],
    top_k: int = 10,
    query_filter: Optional[qm.Filter] = None,
):
    """
    Búsqueda vectorial con filtro opcional (para híbrido semántico + full-text/keyword).
    Usa query_points (API moderna).
    """
    c = get_client()
    res = c.query_points(
        collection_name=COLLECTION,
        query=vector,
        limit=top_k,
        with_payload=True,
        with_vectors=False,
        query_filter=query_filter,   # <-- ahora acepta filtros
    )
    return res.points


# --- Helpers de filtros (útiles desde api/service.py) ---

def make_title_ft_filter(text: str) -> qm.Filter:
    """
    Full-text sobre 'title' (requiere índice de texto creado).
    """
    return qm.Filter(
        must=[
            qm.FieldCondition(
                key="title",
                match=qm.MatchText(text=text),
            )
        ]
    )


def make_source_filter(source: str) -> qm.Filter:
    """
    Coincidencia exacta por 'source' (keyword index).
    """
    return qm.Filter(
        must=[
            qm.FieldCondition(
                key="source",
                match=qm.MatchValue(value=source),
            )
        ]
    )


def combine_filters_and(*conds: qm.Filter) -> qm.Filter:
    """
    Combina varios filtros en un AND lógico (une todos sus 'must').
    """
    must_conditions = []
    for f in conds:
        # Cada Filter puede tener must/should/must_not; aquí unimos solo 'must' para simplicidad
        if f and getattr(f, "must", None):
            must_conditions.extend(f.must)
    return qm.Filter(must=must_conditions) if must_conditions else qm.Filter()
