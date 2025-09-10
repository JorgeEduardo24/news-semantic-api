import os
from functools import lru_cache
from typing import List
import numpy as np

# Carga .env si existe, pero SIN sobrescribir variables ya definidas (p. ej., en CI)
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except Exception:
    pass

# DEFAULT seguro = fastembed
BACKEND = os.getenv("EMBEDDING_BACKEND", "fastembed")
if BACKEND is None:
    BACKEND = "fastembed"
BACKEND = BACKEND.strip().lower()

# Si alguien deja "hashing" por accidente, mapéalo a fastembed
if BACKEND in ("hashing", "hash"):
    BACKEND = "fastembed"

# Modelo por defecto (384 dims para MiniLM)
MODEL_NAME = os.getenv(
    "MODEL_NAME",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    """Normaliza por fila (evita división por cero)."""
    if mat.size == 0:
        return mat
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


# ------------------------------
# Backends
# ------------------------------
if BACKEND == "fastembed":
    from fastembed import TextEmbedding

    @lru_cache(maxsize=1)
    def _embedder() -> TextEmbedding:
        # Crea y cachea una sola instancia del modelo
        return TextEmbedding(model_name=MODEL_NAME)

    @lru_cache(maxsize=1)
    def _embedding_dim() -> int:
        # fastembed no siempre expone dimensión; probamos con un embed mínimo
        try:
            v = list(_embedder().embed(["__dim_probe__"], batch_size=1))[0]
            return len(v)
        except Exception:
            # Fallback defensivo
            arr = np.array(list(_embedder().embed(["__dim_probe__"])), dtype=np.float32)
            return int(arr.shape[1]) if arr.ndim == 2 else 0

    def embed_texts(texts: List[str]) -> np.ndarray:
        """Devuelve matriz (n, d) float32 L2-normalizada. Seguro con lista vacía."""
        if not texts:
            return np.empty((0, _embedding_dim()), dtype=np.float32)
        vecs = list(_embedder().embed(texts, batch_size=32))
        arr = np.array(vecs, dtype=np.float32)
        return _l2_normalize(arr)

elif BACKEND == "sentence-transformers":
    from sentence_transformers import SentenceTransformer

    @lru_cache(maxsize=1)
    def _embedder() -> SentenceTransformer:
        # Crea y cachea una sola instancia del modelo
        return SentenceTransformer(MODEL_NAME)

    @lru_cache(maxsize=1)
    def _embedding_dim() -> int:
        try:
            return int(_embedder().get_sentence_embedding_dimension())
        except Exception:
            # Fallback defensivo
            arr = _embedder().encode(["__dim_probe__"])
            arr = np.asarray(arr)
            return int(arr.shape[1]) if arr.ndim == 2 else 0

    def embed_texts(texts: List[str]) -> np.ndarray:
        """Devuelve matriz (n, d) float32 L2-normalizada. Seguro con lista vacía."""
        if not texts:
            return np.empty((0, _embedding_dim()), dtype=np.float32)
        vecs = _embedder().encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=False)
        arr = np.array(vecs, dtype=np.float32)
        return _l2_normalize(arr)

else:
    raise ValueError(
        f"Embedding backend '{BACKEND}' no soportado. Usa 'fastembed' o 'sentence-transformers'."
    )


# ------------------------------
# API conveniente (single/batch)
# ------------------------------
def embed(text: str) -> List[float]:
    """
    Embedding para un solo texto. Devuelve lista[float] L2-normalizada.
    """
    # embed_texts siempre devuelve (n,d); aquí n=1
    arr = embed_texts([text])
    if arr.shape[0] == 0:
        return []
    return arr[0].tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Embedding por lotes. Devuelve lista de listas (n, d) L2-normalizada.
    Maneja lista vacía devolviendo [].
    """
    if not texts:
        return []
    arr = embed_texts(texts)
    return arr.tolist()


__all__ = [
    "embed_texts",  # np.ndarray (n,d) float32 normalizado
    "embed",        # List[float]
    "embed_batch",  # List[List[float]]
    "_embedding_dim",
    "BACKEND",
    "MODEL_NAME",
]
