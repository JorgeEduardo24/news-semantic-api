from __future__ import annotations

import datetime as dt
import hashlib
import logging
from typing import Optional

import feedparser  # type: ignore[import-untyped]
import trafilatura

from api.service import index_one  # Orquestador existente: hace embedding + upsert

log = logging.getLogger(__name__)

# Evitar repetidos dentro de la misma ejecución
def _dedup(url: str) -> str:
    """Hash estable para deduplicar por URL dentro de una ejecución."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def _best_published(entry) -> Optional[dt.datetime]:
    """
    Toma la mejor fecha disponible del feed y la normaliza a datetime con tz UTC.
    """
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            # tuple estilo time.struct_time → (Y, m, d, H, M, S, ...)
            return dt.datetime(*parsed[:6], tzinfo=dt.timezone.utc)
    return None


def _extract_clean(url: str, summary_fallback: str) -> str:
    """
    1) Intenta descargar HTML real con trafilatura.fetch_url() y extraer texto limpio.
    2) Si falla o no hay cuerpo, usa el summary/description del feed como fallback.
    """
    try:
        downloaded = trafilatura.fetch_url(url, no_ssl=True, timeout=10)
        if downloaded:
            extracted = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
            )
            if extracted and extracted.strip():
                # Normalización mínima
                text = extracted.strip()
                return " ".join(text.split())
    except Exception as e:
        # No detenemos la ingesta por un artículo malo
        log.debug("Fallo extrayendo HTML para %s: %s", url, e)

    fallback = (summary_fallback or "").strip()
    return " ".join(fallback.split())


def ingest_feed(feed_url: str, limit: int = 20, lang: Optional[str] = None) -> int:
    """
    Descarga un feed RSS/Atom, limpia y **indexa** cada ítem en Qdrant vía index_one().
    Devuelve la cantidad total efectivamente indexada (N).
    """
    parsed = feedparser.parse(feed_url)
    total = 0
    seen: set[str] = set()
    host = (
        feed_url.split("/")[2]  # rápido y suficiente para http(s)://
        if "://" in feed_url
        else feed_url
    )

    for entry in parsed.entries[:limit]:
        url = getattr(entry, "link", None) or getattr(entry, "id", None)
        title = getattr(entry, "title", None)
        if not url or not title:
            continue

        # Deduplicación local por URL
        d = _dedup(url)
        if d in seen:
            continue
        seen.add(d)

        published_at = _best_published(entry)

        # Fallback textual si no se logra extraer del HTML
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        content = _extract_clean(url, summary)

        # Documento según contrato de /index
        doc = {
            "title": title,
            "url": url,
            "source": host,
            "published_at": published_at,  
            "content": content,
            "language": lang or "es",
        }

        try:
            # index_one debe ser idempotente por URL en tu capa service/cliente
            index_one(doc)
            total += 1
        except Exception as e:
            # En producción: log estructurado + request_id/trace_id
            log.warning("No se pudo indexar %s: %s", url, e)
            continue

    return total
