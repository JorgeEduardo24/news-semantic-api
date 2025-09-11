import datetime as dt
import time
from typing import Annotated, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, HttpUrl

from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram

from clients.qdrant_client import ensure_collection
from ingest.rss import ingest_feed

# Servicio 
from api.service import index_one, search_query, get_doc_by_url
# Builders BONUS
from api.service import build_storyline, build_perspective, build_graph
# Schemas BONUS (para response_model)
from api.schemas import StorylineResponse, PerspectiveResponse, GraphResponse

app = FastAPI(title="News Semantic API", version="0.2.0")


# -----------------------------
# Modelos existentes (públicos)
# -----------------------------
class ArticleIn(BaseModel):
    title: str
    url: HttpUrl
    source: str
    published_at: Optional[dt.datetime] = None
    content: str
    language: Optional[str] = "es"


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    source: str
    score: float
    snippet: Optional[str] = None
    published_at: Optional[dt.datetime] = None


# -----------------------------
# Métricas Prometheus
# -----------------------------
INDEX_TOTAL = Counter("index_total", "Total de artículos indexados")
SEARCH_TOTAL = Counter("search_total", "Total de búsquedas semánticas")
INGEST_TOTAL = Counter("ingest_total", "Total de ingestas realizadas")
SEARCH_LATENCY = Histogram("search_latency_seconds", "Latencia de /search en segundos")

Instrumentator().instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

# -----------------------------
# Startup: esperar Qdrant + /metrics
# -----------------------------
@app.on_event("startup")
def _init_collections():
    # Espera simple a Qdrant
    last = None
    for i in range(30):  # ~30s
        try:
            ensure_collection()
            break
        except Exception as e:
            last = e
            time.sleep(1 + i * 0.2)
    else:
        raise RuntimeError(f"Qdrant no se pudo inicializar a tiempo: {last}")



# -----------------------------
# Endpoints base (existentes)
# -----------------------------
@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/readyz")
def readyz():
    return {"ready": True}


@app.post("/index")
def index_article(item: ArticleIn):
    """
    Indexa un artículo en Qdrant (embedding título+contenido).
    Incrementa métrica INDEX_TOTAL.
    """
    index_one(item.model_dump())
    INDEX_TOTAL.inc()
    return {"indexed": True, "url": str(item.url)}


@app.get("/search", response_model=List[SearchResult])
def search(
    q: str,
    k: int = 10,
    title_contains: Optional[str] = Query(None, description="Filtro full-text en título"),
    source: Optional[str] = Query(None, description="Fuente exacta (payload.source)"),
):
    """
    Búsqueda semántica con filtros opcionales (title_contains, source).
    Mide latencia y cuenta invocaciones.
    """
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="q muy corto")

    with SEARCH_LATENCY.time():
        results = [SearchResult(**x) for x in search_query(
            q, k, title_contains=title_contains, source=source
        )]
    SEARCH_TOTAL.inc()
    return results


@app.api_route("/ingest/feed", methods=["GET", "POST"])
def ingest_feed_endpoint(
    url: Annotated[HttpUrl, Query(description="URL del feed RSS")],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    lang: Annotated[Optional[str], Query(description="Idioma deseado (opcional)")] = None,
):
    """
    Ingesta desde feed RSS y devuelve cuántos artículos se indexaron.
    Incrementa INGEST_TOTAL con el total indexado.
    """
    total = ingest_feed(str(url), limit=limit, lang=lang)
    try:
        # suma por cantidad de items procesados
        INGEST_TOTAL.inc(total)
    except Exception:
        # fallback defensivo (por si total no es numérico)
        INGEST_TOTAL.inc()
    return {"indexed": total, "feed": str(url)}


@app.get("/doc", response_model=ArticleIn)
def get_doc(
    url: Annotated[HttpUrl, Query(description="URL exacta del documento a recuperar")],
    max_chars: Annotated[int, Query(ge=0, description="Trunca content a N chars (0 = sin truncar)")] = 0,
):
    """
    Recupera el documento completo por URL exacta (payload.url).
    Permite truncar el contenido para evitar respuestas muy grandes.
    """
    doc = get_doc_by_url(str(url))
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Truncado opcional del contenido
    if max_chars and isinstance(doc.get("content"), str):
        doc["content"] = doc["content"][:max_chars]

    return doc  # FastAPI lo valida contra ArticleIn


# -----------------------------
# Endpoints BONUS
# -----------------------------
@app.get("/storyline", response_model=StorylineResponse)
def get_storyline(
    q: Annotated[str, Query(min_length=2, description="Consulta semántica base")],
    k: int = 20,
    title_contains: Optional[str] = Query(None, description="Subcadena en título"),
    source: Optional[str] = Query(None, description="Fuente exacta"),
    date_from: Optional[str] = Query(None, description="ISO 8601 (YYYY-MM-DD o fecha/hora)"),
    date_to: Optional[str] = Query(None, description="ISO 8601 (YYYY-MM-DD o fecha/hora)"),
):
    """
    Agrupa top-N resultados en hilos (clusters) por similitud y orden temporal.
    """
    filters = {
        "title_contains": title_contains,
        "source": source,
        "date_from": date_from,
        "date_to": date_to,
    }
    return build_storyline(q=q, k=k, **{k: v for k, v in filters.items() if v is not None})


@app.get("/analysis/perspective", response_model=PerspectiveResponse)
def get_perspective(
    q: Annotated[str, Query(min_length=2, description="Consulta semántica base")],
    sources: Optional[str] = Query(None, description="CSV de fuentes a comparar"),
    k: int = 40,
    title_contains: Optional[str] = Query(None, description="Subcadena en título"),
    date_from: Optional[str] = Query(None, description="ISO 8601 (YYYY-MM-DD o fecha/hora)"),
    date_to: Optional[str] = Query(None, description="ISO 8601 (YYYY-MM-DD o fecha/hora)"),
):
    """
    Compara cobertura por fuente: entidades, tono (heurístico), términos y volumen.
    """
    filters = {"title_contains": title_contains, "date_from": date_from, "date_to": date_to}
    sources_filter = [s.strip() for s in sources.split(",")] if sources else None
    return build_perspective(q=q, sources_filter=sources_filter, k=k, **{k: v for k, v in filters.items() if v is not None})


@app.get("/graph/entities", response_model=GraphResponse)
def get_graph(
    q: Annotated[str, Query(min_length=2, description="Consulta semántica base")],
    k: int = 30,
    title_contains: Optional[str] = Query(None, description="Subcadena en título"),
    source: Optional[str] = Query(None, description="Fuente exacta"),
    date_from: Optional[str] = Query(None, description="ISO 8601 (YYYY-MM-DD o fecha/hora)"),
    date_to: Optional[str] = Query(None, description="ISO 8601 (YYYY-MM-DD o fecha/hora)"),
):
    """
    Grafo de co-ocurrencia de entidades principales (a nivel documento).
    """
    filters = {
        "title_contains": title_contains,
        "source": source,
        "date_from": date_from,
        "date_to": date_to,
    }
    return build_graph(q=q, k=k, **{k: v for k, v in filters.items() if v is not None})
