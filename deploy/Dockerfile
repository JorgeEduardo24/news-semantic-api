# syntax=docker/dockerfile:1.6

############################
# Builder
############################
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copia manifest de dependencias primero (para cache)
COPY pyproject.toml poetry.lock* ./

# Instala Poetry y genera/actualiza lock + exporta requirements
RUN pip install --upgrade pip && pip install "poetry==1.8.3"
RUN poetry lock --no-interaction --no-ansi
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes
# (debug: fallar si uvicorn no está)
RUN echo '--- requirements.txt ---' && grep -i '^uvicorn' requirements.txt || (echo "uvicorn NO está en requirements.txt" && cat requirements.txt && exit 2)

# Crea venv e instala dependencias
RUN python -m venv /opt/venv && . /opt/venv/bin/activate && \
    pip install --no-cache-dir -r requirements.txt

# ====== Instalar modelo spaCy ES en el venv ======
RUN . /opt/venv/bin/activate && \
    python -m pip install --no-cache-dir \
      https://github.com/explosion/spacy-models/releases/download/es_core_news_md-3.8.0/es_core_news_md-3.8.0-py3-none-any.whl && \
    python -m spacy validate
# ==========================================================

# Copia código
COPY api/ api/
COPY clients/ clients/
COPY embedding/ embedding/
COPY ingest/ ingest/
COPY README.md ./

############################
# Runtime
############################
FROM python:3.12-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl tini libgomp1 netcat-traditional && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/api /app/api
COPY --from=builder /app/clients /app/clients
COPY --from=builder /app/embedding /app/embedding
COPY --from=builder /app/ingest /app/ingest
COPY --from=builder /app/README.md /app/README.md
COPY --chmod=755 deploy/docker/entrypoint.sh /entrypoint.sh

ENV PATH="/opt/venv/bin:${PATH}"
ENTRYPOINT ["/usr/bin/tini","-g","--","/entrypoint.sh"]
