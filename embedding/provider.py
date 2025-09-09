import os
from functools import lru_cache
from typing import List
import numpy as np

os.environ.setdefault("EMBEDDING_BACKEND", "fastembed")

BACKEND = os.getenv("EMBEDDING_BACKEND", "fastembed").lower()

if BACKEND == "fastembed":
    from fastembed import TextEmbedding
    MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 384 dims

    @lru_cache(maxsize=1)
    def _embedder() -> TextEmbedding:
        return TextEmbedding(model_name=MODEL_NAME)

    def _l2_normalize(mat: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return mat / norms

    def embed_texts(texts: List[str]) -> np.ndarray:
        vecs = list(_embedder().embed(texts, batch_size=32))
        arr = np.array(vecs, dtype=np.float32)
        return _l2_normalize(arr)
    
elif BACKEND == "sentence-transformers":
    from sentence_transformers import SentenceTransformer

    MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    @lru_cache(maxsize=1)
    def _embedder() -> SentenceTransformer:
        return SentenceTransformer(MODEL_NAME)

    def _l2_normalize(mat: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return mat / norms

    def embed_texts(texts: List[str]) -> np.ndarray:
        vecs = _embedder().encode(texts, batch_size=32, show_progress_bar=False)
        arr = np.array(vecs, dtype=np.float32)
        return _l2_normalize(arr)


else:
    raise ValueError(f"Embedding backend '{BACKEND}' no soportado. Usa 'fastembed' o 'sentence-transformers'.")