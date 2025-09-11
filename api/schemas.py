from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl
import datetime as dt

# Forma estándar de una noticia
class Article(BaseModel):
    title: str
    url: HttpUrl
    source: str
    published_at: Optional[dt.datetime] = None
    snippet: Optional[str] = None
    score: Optional[float] = None

# Artículo dentro de un cluster de la storyline.
class StoryItem(BaseModel):
    title: str
    url: HttpUrl
    source: str
    published_at: Optional[dt.datetime] = None
    score: Optional[float] = None

# Grupo de artículos similares
class StoryCluster(BaseModel):
    cluster_id: int
    title: str
    timespan: List[Optional[dt.datetime]]  # [min,max]
    items: List[StoryItem]

# Ligar el resultado con la consulta que lo generó.
class StorylineResponse(BaseModel):
    query: str
    clusters: List[StoryCluster]

# “reporte” de una fuente en /analysis/perspective
# comparar enfoques entre medios (¿quién cubre más?, ¿qué nombres repiten?, ¿qué tono?).
class SourcePerspective(BaseModel):
    source: str
    volume: int
    top_entities: List[str]
    avg_sentiment: float  # -1..+1 (heurística simple)
    top_terms: List[str]
    time_histogram: Dict[str, int]  # yyyy-mm-dd -> count

# respuesta de /analysis/perspective
# agrupar comparativas por medio en una sola respuesta.
class PerspectiveResponse(BaseModel):
    query: str
    sources: List[SourcePerspective]

# Una entidad (PERSON/ORG/LOC/MISC) detectada en las noticias
class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # PERSON, ORG, LOC, MISC

# Co-ocurrencia entre dos entidades. Mostrar conexiones fuertes (quién aparece con quién y cuántas veces).
class GraphEdge(BaseModel):
    source: str
    target: str
    weight: int

# Respuesta de /graph/entities | Todo lo necesario para renderizar el grafo en cliente
class GraphResponse(BaseModel):
    query: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]
