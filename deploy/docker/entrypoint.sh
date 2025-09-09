#!/usr/bin/env bash
set -euo pipefail

VENV="/opt/venv"
if [ -x "$VENV/bin/python" ]; then
  export PATH="$VENV/bin:$PATH"
fi

echo "[entrypoint] PATH=$PATH"
echo "[entrypoint] python=$(command -v python)"
python - <<'PY'
import sys, os
print("[entrypoint] sys.executable=", sys.executable)
print("[entrypoint] sys.path[0:3]=", sys.path[:3])
PY

# Variables esperadas
: "${EMBEDDING_BACKEND:=fastembed}"
: "${MODEL_NAME:=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2}"
: "${QDRANT_HOST:=news-demo-qdrant}"
: "${QDRANT_PORT:=6333}"
: "${UVICORN_WORKERS:=2}"
: "${PORT:=8000}"

echo "[entrypoint] Starting News Semantic API"
echo "[entrypoint] EMBEDDING_BACKEND=${EMBEDDING_BACKEND} MODEL_NAME=${MODEL_NAME} QDRANT=${QDRANT_HOST}:${QDRANT_PORT}"

# (opcional) espera corta a Qdrant
for i in $(seq 1 30); do
  if nc -zv "${QDRANT_HOST}" "${QDRANT_PORT}" >/dev/null 2>&1; then
    break
  fi
  echo "[entrypoint] waiting qdrant ${QDRANT_HOST}:${QDRANT_PORT} ($i/30)"
  sleep 1
done

exec python -m uvicorn api.main:app --host 0.0.0.0 --port "${PORT}" --workers "${UVICORN_WORKERS}"

