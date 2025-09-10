# clients/qdrant_client.py
import os
from typing import List, Optional
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from qdrant_client.http.models import TextIndexParams, PayloadSchemaType

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION = os.getenv("QDRANT_COLLECTION", "news")

# Debe coincidir con el modelo por defecto en embedding/provider.py
# (paraphrase-multilingual-MiniLM-L12-v2 => 384 dims)
VECTOR_SIZE = 384


def get_client() -> QdrantClient:
    """
    Crea el cliente Qdrant.
    - https=False para localhost/cluster interno (cámbialo si usas TLS).
    - prefer_grpc=False: HTTP por simplicidad; activa gRPC si lo necesitas.
    """
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
                tokenizer="latin",   # usa "multilingual" si mezclas es/en/pt a fondo
                min_token_len=2,
                max_token_len=24,
                lowercase=True,
            ),
        )
    except Exception:
        # ya existe o el servidor no soporta -> ignoramos
        pass

    # Índice keyword en 'source' (útil para filtros exactos por fuente)
    try:
        c.create_payload_index(
            collection_name=COLLECTION,
            field_name="source",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception:
        pass


def ensure_collection() -> None:
    """
    Asegura que la colección exista y tenga la configuración/índices esperados.
    Es idempotente.
    """
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

    # Crear índices (sean nuevos o ya existentes)
    _ensure_payload_indices(c)


def upsert_article(vec_id: Optional[str], vector: List[float], payload: dict) -> None:
    """
    Inserta/actualiza un punto. Si no pasas 'vec_id', genera un UUID.
    Para idempotencia por URL/título, genera el ID determinístico aguas arriba.
    """
    c = get_client()
    pid = vec_id or str(uuid4())
    point = qm.PointStruct(id=pid, vector=vector, payload=payload)
    c.upsert(collection_name=COLLECTION, points=[point])


def search(
    vector: List[float],
    top_k: int = 10,
    query_filter: Optional[qm.Filter] = None,
):
    """
    Búsqueda vectorial (cosine) con filtro opcional para híbrido (full-text/keyword).
    Usa la API moderna 'query_points'.
    """
    c = get_client()
    res = c.query_points(
        collection_name=COLLECTION,
        query=vector,
        limit=top_k,
        with_payload=True,
        with_vectors=False,
        query_filter=query_filter,
    )
    return res.points


# --- Helpers de filtros (útiles desde api/service.py) -------------------------

def make_title_ft_filter(text: str) -> qm.Filter:
    """
    Full-text sobre 'title' (requiere el índice de texto creado).
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
    Coincidencia exacta por 'source' (requiere índice keyword).
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
    Combina varios filtros en un AND lógico (concatena sus 'must').
    """
    must_conditions = []
    for f in conds:
        if f and getattr(f, "must", None):
            must_conditions.extend(f.must)
    return qm.Filter(must=must_conditions) if must_conditions else qm.Filter()
