import os

os.environ["EMBEDDING_BACKEND"] = "hashing"  # rápido y sin red para test (nO DESCARGA DE LOS MODELOS)
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

# Pruebas Unitarias
def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True

# Valida que vuelve al menos 1 resultado
def test_index_and_search():
    doc = {
        "title": "Demo",
        "url": "https://example.com/test",
        "source": "tests",
        "content": "Texto de prueba sobre economía y Colombia.",
    }
    r = client.post("/index", json=doc)
    assert r.status_code == 200

    r = client.get("/search", params={"q": "economía", "k": 3})
    assert r.status_code == 200
    res = r.json()
    assert isinstance(res, list)
    assert len(res) >= 1
    assert res[0]["url"] == "https://example.com/test"
