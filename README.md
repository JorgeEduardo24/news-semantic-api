# News Semantic API

- **Stack**: FastAPI + Qdrant (vector DB) + FastEmbed (ONNX, CPU)  
- **Embeddings**: `qdrant/all-MiniLM-L6-v2-onnx-Q` (dim=384, L2-normalized)
- **Ingesta**: RSS (feedparser) + extracción limpia (trafilatura)
- **TODO**

## Dev
```bash
docker compose -f docker-compose.local.yml up -d    # Levanta Qdrant (localhost:6333)
export EMBEDDING_BACKEND=fastembed
poetry run uvicorn api.main:app --host 0.0.0.0 --port 8080

