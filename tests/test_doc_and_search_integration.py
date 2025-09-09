import os, pytest, time
from fastapi.testclient import TestClient
from api.main import app
from clients.qdrant_client import ensure_collection
from api.service import index_one

pytestmark = pytest.mark.integration

def qdrant_available():
    try:
        ensure_collection()
        return True
    except Exception:
        return False

@pytest.mark.skipif(not qdrant_available(), reason="Qdrant no accesible")
def test_index_search_doc_flow():
    client = TestClient(app)
    # Indexa dos docs
    doc1 = {"title": "Argentina derrota histórica",
            "url": "https://control/a1", "source": "control",
            "content": "Contenido A", "language": "es"}
    doc2 = {"title": "Otro tema", "url": "https://control/b2",
            "source": "control", "content": "Contenido B", "language": "es"}
    index_one(doc1); index_one(doc2)
    time.sleep(0.3)  # pequeño margen

    # search con filtro por título
    r = client.get("/search", params={"q": "Argentina", "k": 5, "title_contains": "Argentina"})
    assert r.status_code == 200
    data = r.json()
    assert any("Argentina" in d["title"] for d in data)

    # doc por URL y truncado
    r = client.get("/doc", params={"url": doc1["url"], "max_chars": 5})
    assert r.status_code == 200
    assert r.json()["content"] == "Conte"
