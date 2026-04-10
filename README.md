# News Semantics API

API HTTP para **indexación semántica de noticias**, **búsqueda por similitud** y **análisis agregado** (hilos narrativos, perspectiva por fuente y grafo de entidades) sobre un almacén vectorial [Qdrant](https://qdrant.tech/). Pensada para integrarse en pipelines de medios, agregadores o herramientas de monitorización de cobertura.

> **Nota sobre el nombre del repositorio:** el paquete Python y artefactos pueden figurar como `news-semantic-api` (singular); el producto se documenta aquí como **News Semantics API**.

---

## Tabla de contenidos

1. [Visión y casos de uso](#visión-y-casos-de-uso)
2. [Arquitectura](#arquitectura)
3. [Stack tecnológico](#stack-tecnológico)
4. [Requisitos](#requisitos)
5. [Desarrollo local](#desarrollo-local)
6. [Variables de entorno](#variables-de-entorno)
7. [API HTTP](#api-http)
8. [Modelo de datos y vector store](#modelo-de-datos-y-vector-store)
9. [Ingesta RSS](#ingesta-rss)
10. [Observabilidad](#observabilidad)
11. [Contenedores y despliegue](#contenedores-y-despliegue)
12. [CI/CD](#cicd)
13. [Calidad de código y pruebas](#calidad-de-código-y-pruebas)
14. [Limitaciones y buenas prácticas](#limitaciones-y-buenas-prácticas)

---

## Visión y casos de uso

- **Búsqueda semántica** sobre titulares y cuerpo de artículo, con filtros opcionales por texto en título y por fuente.
- **Indexación idempotente** por URL (misma URL → mismo punto lógico en Qdrant).
- **Ingesta desde RSS/Atom** con extracción de texto principal (HTML) y fallback a resumen del feed.
- **Capa de análisis** sobre los resultados de búsqueda: agrupación en hilos (*storyline*), comparación heurística entre medios (*perspective*) y grafo de co-ocurrencia de entidades (*graph*).

---

## Arquitectura

- **FastAPI** expone endpoints REST y métricas; el arranque espera a que Qdrant y la colección estén disponibles (reintentos en *startup*).
- **Embeddings** se generan en CPU (ONNX vía FastEmbed por defecto); vectores **L2-normalizados** para similitud coseno estable.
- **Qdrant** almacena vectores y *payload* (metadatos del artículo); índices de payload para filtros de título (*full-text*) y fuente (*keyword*).

---

## Stack tecnológico

| Área | Tecnología |
|------|------------|
| Runtime | Python 3.12 |
| API | FastAPI, Uvicorn, Pydantic v2 |
| Vector DB | `qdrant-client`, Qdrant (HTTP; gRPC desactivado en cliente) |
| Embeddings | **FastEmbed** (por defecto) u opcional **sentence-transformers** (`EMBEDDING_BACKEND`) |
| Ingesta | `feedparser`, `trafilatura`, `beautifulsoup4` |
| NLP análisis | spaCy (`es_core_news_md` en imagen Docker), scikit-learn (TF-IDF, clustering) |
| Gráfos / utilidades | NetworkX (dependencia del proyecto) |
| Métricas | `prometheus-fastapi-instrumentator`, `prometheus-client` |
| Gestión de deps | Poetry |

---

## Requisitos

- **Python 3.12** (ver `pyproject.toml`).
- **Qdrant** accesible (local o remoto). Para desarrollo rápido: `docker-compose` incluido.
- Para análisis con calidad óptima en español: modelo spaCy `es_core_news_md` (instalado en la imagen Docker; en local ver sección de desarrollo).

---

## Desarrollo local

### 1. Levantar Qdrant

```bash
docker compose -f docker-compose.local.yml up -d
```

Persistencia en `./.data/qdrant`. API Qdrant: `http://localhost:6333`.

### 2. Instalar dependencias (Poetry)

```bash
poetry install --with dev
```

### 3. Modelo spaCy (recomendado fuera de Docker)

Para que `/analysis/perspective` y `/graph/entities` usen NER completo:

```bash
poetry run python -m spacy download es_core_news_md
```

Si el modelo no está, el código hace *fallback* a `spacy.blank("es")` (comportamiento degradado).

### 4. Ejecutar la API

```bash
make run
```

Por defecto escucha en `0.0.0.0:8080` con `EMBEDDING_BACKEND=fastembed`. Equivalente:

```bash
EMBEDDING_BACKEND=fastembed poetry run uvicorn api.main:app --host 0.0.0.0 --port 8080
```

### 5. Comprobar salud

```bash
curl -s http://localhost:8080/healthz
curl -s http://localhost:8080/readyz
```

### Utilidades Makefile

| Objetivo | Descripción |
|----------|-------------|
| `make run` | Servidor de desarrollo en puerto 8080 |
| `make fmt` | Ruff check --fix + format |
| `make lint` | Ruff + mypy |
| `make test` | Pytest |
| `make cov` | Cobertura sobre `api`, `clients`, `embedding` |
| `make reset-qdrant` | Elimina la colección `news` en Qdrant local (destructivo) |

---

## Variables de entorno

| Variable | Descripción | Valor por defecto típico |
|----------|-------------|---------------------------|
| `EMBEDDING_BACKEND` | `fastembed` o `sentence-transformers` | `fastembed` |
| `MODEL_NAME` | Identificador del modelo de embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `QDRANT_HOST` | Host Qdrant | `localhost` (código cliente) |
| `QDRANT_PORT` | Puerto API Qdrant | `6333` |
| `QDRANT_COLLECTION` | Nombre de la colección | `news` |

El módulo `embedding/provider.py` carga `.env` con `override=False` para no pisar variables ya fijadas (por ejemplo en CI).

En **Docker** (`deploy/docker/entrypoint.sh`): `PORT` (por defecto `8000`), `UVICORN_WORKERS`, y espera activa a Qdrant vía `nc` antes de arrancar Uvicorn.

---

## API HTTP

Base: prefijo raíz (sin `/api/v1`); versionado actual de la app: **0.2.0** (ver `api/main.py`).

### Operativos y salud

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/healthz` | *Liveness*: servicio arriba |
| GET | `/readyz` | *Readiness* simplificado |
| GET | `/metrics` | Métricas Prometheus (no aparece en OpenAPI) |

### Indexación y búsqueda

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/index` | Cuerpo JSON: `title`, `url`, `source`, `content`, opcional `published_at`, `language`. Indexa título+contenido |
| GET | `/search` | Query `q` (mín. 2 caracteres), `k`, opcional `title_contains`, `source`. Lista de resultados con `score` y *snippet* |
| GET o POST | `/ingest/feed` | Query: `url` del RSS, `limit`, `lang`. Descarga feed, extrae texto e indexa |
| GET | `/doc` | Query: `url` exacta; opcional `max_chars` para truncar `content` |

### Análisis (capa “bonus” / agregada)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/storyline` | Agrupa resultados en clusters (similitud + orden temporal) |
| GET | `/analysis/perspective` | Por fuente: entidades, términos TF-IDF, tono heurístico, volumen, histograma temporal |
| GET | `/graph/entities` | Grafo de co-ocurrencia de entidades a nivel documento |

**Contrato de error:** por ejemplo `q` demasiado corto en `/search` → `400`; documento no encontrado en `/doc` → `404`.

La documentación interactiva está disponible en `/docs` (Swagger UI) y `/redoc` cuando ejecutas la aplicación.

---

## Modelo de datos y vector store

- **Dimensión del vector:** 384 (alineada con `VECTOR_SIZE` en `clients/qdrant_client.py` y el modelo MiniLM multilingüe).
- **Distancia:** coseno (`Cosine` en Qdrant).
- **ID de punto:** UUID determinista v5 a partir de la URL (`NAMESPACE_URL`), de modo que reindexar la misma URL actualiza el mismo punto.
- **Filtros:** combinación de búsqueda vectorial con `MatchText` sobre `title` y `MatchValue` sobre `source`, apoyados en índices de payload creados en `ensure_collection()`.
- **Fechas en análisis:** filtros `date_from` / `date_to` se aplican en memoria sobre `published_at` tras la búsqueda vectorial.

---

## Ingesta RSS

Flujo en `ingest/rss.py`:

1. Parseo del feed con `feedparser`.
2. Por cada entrada: URL, título, fecha preferente (`published` / `updated` / `created`).
3. Contenido: `trafilatura` sobre el HTML del artículo; si falla, resumen del feed.
4. `source` se deriva del host de la URL del feed.
5. Indexación vía `index_one` (mismas reglas que `/index`).

---

## Observabilidad

- **Prometheus:** endpoint `/metrics`; contadores personalizados (`index_total`, `search_total`, `ingest_total`) e histograma `search_latency_seconds` para `/search`.
- **Helm:** `ServiceMonitor` opcional (`deploy/helm/news-semantic-api/values.yaml`) para kube-prometheus-stack.
- Ejemplo de manifiesto adicional: `monitoring-news-api.yaml` en la raíz del repositorio.

---

## Contenedores y despliegue

- **Dockerfile** (`deploy/Dockerfile`): multi-stage, Poetry → `requirements.txt`, venv en `/opt/venv`, instalación de `es_core_news_md`, entrada con `tini` + `entrypoint.sh`.
- **Helm** (`deploy/helm/news-semantic-api/`): Deployment, Service, Ingress opcional, HPA, Secret/ConfigMap; valores por entorno en `values.dev.yaml`, `values.gke.yaml`.
- **Infraestructura como código:** Terraform bajo `infra/terraform/gcp/dev/` (ajustar *backend* y variables según tu organización).

---

## CI/CD

- **Pull requests** (`.github/workflows/ci-pr.yml`): instalación con Poetry, `ruff check`, `pytest`.
- Otros flujos en `.github/workflows/`: pruebas adicionales, plan/aplicación Terraform, CD a `main`, según la configuración del repositorio.

---

## Calidad de código y pruebas

```bash
make lint    # ruff + mypy
make test    # pytest
make cov     # cobertura
```

Los tests pueden asumir Qdrant en `localhost:6333` (ver `tests/conftest.py` y variables forzadas para embeddings).

---

## Limitaciones y buenas prácticas

1. **Embeddings y modelo:** cambiar `MODEL_NAME` sin alinear la dimensión en Qdrant implica recrear la colección o migrar datos; mantener coherencia con `VECTOR_SIZE`.
2. **Análisis de tono** en `/analysis/perspective` es **heurístico** (lexicón reducido), no un clasificador de sentimiento entrenado.
3. **NER:** depende de spaCy y del modelo español; textos muy largos se recortan en extracción de entidades.
4. **Grafo de entidades:** co-ocurrencia a nivel documento; no es co-ocurrencia por frase (extensible con segmentación más fina).
5. **Seguridad:** validar orígenes de feeds y URLs en entornos expuestos; la ingesta realiza peticiones HTTP salientes (`trafilatura`, `feedparser`).
6. **Producción:** ajustar recursos (CPU/memoria para ONNX y Uvicorn workers), TLS hacia Qdrant si aplica, y políticas de retención en Qdrant.

---

## Autoría

Proyecto realizado por **Jorge Eduardo Jojoa Erazo (Octubre, 2025)** 
