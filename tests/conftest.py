import os

# Fuerza backend y config antes de importar el código bajo prueba
os.environ.setdefault("EMBEDDING_BACKEND", "fastembed")
os.environ.setdefault("MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# Qdrant local en el job (service container)
os.environ.setdefault("QDRANT_HOST", "localhost")
os.environ.setdefault("QDRANT_PORT", "6333")
