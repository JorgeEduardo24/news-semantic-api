from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl
import datetime as dt

# Compartidos
class Article(BaseModel):
    title: str
    url: HttpUrl
    source: str
    published_at: Optional[dt.datetime] = None
    snippet: Optional[str] = None
    score: Optional[float] = None

# /storyline
class StoryItem(BaseModel):
    title: str
    url: HttpUrl
    source: str
    published_at: Optional[dt.datetime] = None
    score: Optional[float] = None

class StoryCluster(BaseModel):
    cluster_id: int
    title: str
    timespan: List[Optional[dt.datetime]]  # [min,max]
    items: List[StoryItem]

class StorylineResponse(BaseModel):
    query: str
    clusters: List[StoryCluster]

# /analysis/perspective
class SourcePerspective(BaseModel):
    source: str
    volume: int
    top_entities: List[str]
    avg_sentiment: float  # -1..+1 (heurística simple)
    top_terms: List[str]
    time_histogram: Dict[str, int]  # yyyy-mm-dd -> count

class PerspectiveResponse(BaseModel):
    query: str
    sources: List[SourcePerspective]

# /graph/entities
class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # PERSON, ORG, LOC, MISC

class GraphEdge(BaseModel):
    source: str
    target: str
    weight: int

class GraphResponse(BaseModel):
    query: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]
