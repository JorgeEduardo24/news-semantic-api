from __future__ import annotations
from typing import List, Dict, Tuple, Optional
import datetime as dt
from collections import Counter, defaultdict

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
import spacy

# Modelo spaCy (ligero y en español). Cárgalo una vez.
# En Docker instalaremos es_core_news_md.
try:
    _NLP = spacy.load("es_core_news_md")
except Exception:
    _NLP = spacy.blank("es")  # fallback mínimo si no está el modelo (tests rápidos)

# Heurística de sentimiento MUY simple (lexicón corto)
_POS = set(["bueno","positiva","beneficio","mejora","avance","exitoso","crecimiento","favorable"])
_NEG = set(["malo","negativa","crisis","caída","retroceso","fracaso","escándalo","riesgo"])

def _sentiment_score(text: str) -> float:
    tokens = [t.lower() for t in text.split()]
    pos = sum(t in _POS for t in tokens)
    neg = sum(t in _NEG for t in tokens)
    if pos==0 and neg==0:
        return 0.0
    return (pos - neg) / max(1, pos + neg)

def extract_entities(text: str) -> List[Tuple[str,str]]:
    """Devuelve [(label, type)] con types normalizados: PERSON, ORG, LOC, MISC"""
    doc = _NLP(text[:20000])  # recorta por seguridad
    mapping = {"PER":"PERSON","ORG":"ORG","LOC":"LOC","GPE":"LOC","MISC":"MISC","NORP":"MISC","FAC":"LOC"}
    ents = []
    for e in doc.ents:
        t = mapping.get(e.label_, "MISC")
        ents.append((e.text.strip(), t))
    return ents

def tfidf_top_terms(texts: List[str], k: int = 10) -> List[str]:
    if not texts:
        return []
    vec = TfidfVectorizer(
        max_features=2048,
        ngram_range=(1, 2),
        min_df=1,
        norm="l2",
        use_idf=True,
        smooth_idf=True,
        sublinear_tf=False,
    )
    X = vec.fit_transform(texts)                 # (n_docs, vocab)
    scores = np.asarray(X.mean(axis=0)).ravel()  # (vocab,)
    vocab = vec.get_feature_names_out()          # (vocab,)

    order = np.argsort(scores)[::-1]
    top = [vocab[i] for i in order[:k] if scores[i] > 0]
    return top

def cosine_matrix(X: np.ndarray) -> np.ndarray:
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    return Xn @ Xn.T

# --- Normalización de fechas para evitar naive vs aware ---
def _to_utc_aware(d: Optional[dt.datetime]) -> Optional[dt.datetime]:
    """Devuelve datetime aware en UTC. Si d es None, retorna None."""
    if d is None:
        return None
    if d.tzinfo is None:
        # si es naive, asumir UTC
        return d.replace(tzinfo=dt.timezone.utc)
    # convertir a UTC
    return d.astimezone(dt.timezone.utc)

def storyline_clusters(
    embeddings: List[List[float]],
    titles: List[str],
    dates: List[Optional[dt.datetime]],
    k_min: int = 2,
) -> List[List[int]]:
    n = len(embeddings)
    if n == 0:
        return []
    if n < k_min:
        return [list(range(n))]

    X = np.asarray(embeddings, dtype=np.float32)
    # Cosine similarity y distancia
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)
    C = Xn @ Xn.T
    D = 1.0 - C

    # Heurística: ~sqrt(n) clusters
    approx_k = max(2, int(np.sqrt(n)))
    model = AgglomerativeClustering(n_clusters=approx_k, metric="precomputed", linkage="average")
    labels = model.fit_predict(D)

    # Normaliza fechas a UTC aware para ordenar sin errores
    dates_utc = [_to_utc_aware(d) for d in dates]
    utc_min = dt.datetime.min.replace(tzinfo=dt.timezone.utc)

    # Armar clusters y ordenarlos temporalmente
    clusters: List[List[int]] = []
    for lab in sorted(set(labels)):
        idxs = [i for i, l in enumerate(labels) if l == lab]
        idxs.sort(key=lambda i: (dates_utc[i] or utc_min))
        clusters.append(idxs)

    clusters.sort(key=lambda idxs: (dates_utc[idxs[0]] or utc_min))
    return clusters
