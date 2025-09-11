import pytest
from api.service import build_storyline, build_perspective, build_graph
#Monkeypatch -> Inyectar datos falsos
#Verifica que el formato de salida (estructura de datos) sea correcto
def test_storyline_shapes(monkeypatch):
    from api import service as S
    fake_docs = [
        {"title":"Argentina gana","url":"http://a/1","source":"foo","content":"Argentina celebra la victoria","published_at":"2024-01-02T00:00:00"},
        {"title":"Argentina pierde","url":"http://a/2","source":"bar","content":"Argentina sufre derrota","published_at":"2024-01-03T00:00:00"},
        {"title":"Colombia exporta","url":"http://a/3","source":"foo","content":"Colombia aumenta exportaciones","published_at":"2024-01-04T00:00:00"},
    ]
    monkeypatch.setattr(S, "get_topn_for_query", lambda q, k=20, **f: fake_docs)
    res = build_storyline("Argentina", k=3)
    assert res.query == "Argentina"
    assert len(res.clusters) >= 1
    assert len(res.clusters[0].items) >= 1

#Asegura que el builder agrupa por fuente
def test_perspective_basic(monkeypatch):
    from api import service as S
    fake_docs = [
        {"title":"Positivo avance","url":"http://a/1","source":"foo","content":"beneficio mejora avance","published_at":"2024-01-02T00:00:00"},
        {"title":"Riesgo y caída","url":"http://a/2","source":"bar","content":"crisis caída riesgo","published_at":"2024-01-03T00:00:00"},
    ]
    monkeypatch.setattr(S, "get_topn_for_query", lambda q, k=20, **f: fake_docs)
    res = build_perspective("tema", k=2)
    assert res.query == "tema"
    assert {s.source for s in res.sources} == {"foo","bar"}
    assert all(isinstance(s.avg_sentiment, float) for s in res.sources)

#Confirma que el builder devuelve una estructura de grafo válida
def test_graph_basic(monkeypatch):
    from api import service as S
    fake_docs = [
        {"title":"Petro visita Bogotá","url":"http://a/1","source":"foo","content":"Gustavo Petro habló con Claudia López en Bogotá","published_at":"2024-01-02T00:00:00"},
        {"title":"López viaja","url":"http://a/2","source":"bar","content":"Claudia López viajó de Bogotá a Cali","published_at":"2024-01-03T00:00:00"},
    ]
    monkeypatch.setattr(S, "get_topn_for_query", lambda q, k=20, **f: fake_docs)
    res = build_graph("colombia", k=2)
    assert res.query == "colombia"
    assert len(res.nodes) >= 1
    assert len(res.edges) >= 0
