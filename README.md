# News Semantic API

- **Stack**: FastAPI + Qdrant (vector DB) + FastEmbed (ONNX, CPU)  
- **Embeddings**: `qdrant/all-MiniLM-L6-v2-onnx-Q` (dim=384, L2-normalized)
- **Ingesta**: RSS (feedparser) + extracción limpia (trafilatura)
