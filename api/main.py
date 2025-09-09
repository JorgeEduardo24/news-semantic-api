import datetime as dt
import time

from api.service import get_doc_by_url
from typing import Annotated, List, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from api.service import index_one, search_query
from clients.qdrant_client import ensure_collection
from ingest.rss import ingest_feed

app = FastAPI(title="News Semantic API", version="0.2.0")


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


@app.on_event("startup")
def _init_collections():
    # Espera simple a Qdrant
    last = None
    for i in range(30):  # ~30s
        try:
            ensure_collection()
            return
        except Exception as e:
            last = e
            time.sleep(1 + i * 0.2)
    raise RuntimeError(f"Qdrant no se pudo inicializar a tiempo: {last}")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/readyz")
def readyz():
    return {"ready": True}


@app.post("/index")
def index_article(item: ArticleIn):
    # indexamos dejando la URL como string en payload (service se encarga)
    index_one(item.model_dump())
    return {"indexed": True, "url": str(item.url)}


@app.get("/search", response_model=List[SearchResult])
def search(
    q: str,
    k: int = 10,
    title_contains: Optional[str] = Query(None, description="Filtro full-text en título"),
    source: Optional[str] = Query(None, description="Fuente exacta (payload.source)"),
):
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="q muy corto")
    return [SearchResult(**x) for x in search_query(
        q, k, title_contains=title_contains, source=source
    )]




@app.api_route("/ingest/feed", methods=["GET", "POST"])
def ingest_feed_endpoint(
    url: Annotated[HttpUrl, Query(description="URL del feed RSS")],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    lang: Annotated[Optional[str], Query(description="Idioma deseado (opcional)")] = None,
):
    total = ingest_feed(str(url), limit=limit, lang=lang)
    return {"indexed": total, "feed": str(url)}


@app.get("/doc", response_model=ArticleIn)
def get_doc(
    url: Annotated[HttpUrl, Query(description="URL exacta del documento a recuperar")],
    max_chars: Annotated[int, Query(ge=0, description="Trunca content a N chars (0 = sin truncar)")] = 0,
):
    doc = get_doc_by_url(str(url))
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Truncado opcional del contenido para evitar payloads gigantes en UI
    if max_chars and isinstance(doc.get("content"), str):
        doc["content"] = doc["content"][:max_chars]

    return doc  # FastAPI lo valida contra ArticleIn