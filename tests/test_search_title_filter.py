import types
from api.service import search_query
from qdrant_client.http.models import Filter, FieldCondition, MatchText

class Hit:
    def __init__(self, score, payload):
        self.score = score
        self.payload = payload

def test_search_query_title_filter(monkeypatch):
    captured = {}
    def fake_search(vec, top_k=10, query_filter=None):
        captured["top_k"] = top_k
        captured["query_filter"] = query_filter
        return [
            Hit(0.9, {"title": "Argentina gana", "url": "u1", "source": "s", "content": "x"}),
            Hit(0.5, {"title": "Otra cosa", "url": "u2", "source": "s", "content": "y"}),
        ]

    import clients.qdrant_client as qc
    monkeypatch.setattr(qc, "search", fake_search)

    out = search_query("Argentina", k=5, title_contains="Argentina")
    assert out and out[0]["title"].startswith("Argentina")
    assert captured["top_k"] == 5
    # Verifica que usamos MatchText sobre 'title'
    f = captured["query_filter"]
    assert isinstance(f, Filter) and isinstance(f.must[0], FieldCondition)
    assert isinstance(f.must[0].match, MatchText)
    assert f.must[0].key == "title"
