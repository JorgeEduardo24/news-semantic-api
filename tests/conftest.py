import os
# Para que los imports y la app carguen con valores “seguros” en test/CI
# Fuerza backend/modelo para que los imports no fallen
os.environ["EMBEDDING_BACKEND"] = "fastembed"
os.environ["MODEL_NAME"] = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Qdrant cuando corren los tests en CI (service container localhost)
os.environ.setdefault("QDRANT_HOST", "localhost")
os.environ.setdefault("QDRANT_PORT", "6333")
