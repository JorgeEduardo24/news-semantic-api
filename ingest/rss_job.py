from typing import Optional

import feedparser  # type: ignore[import-untyped]
import trafilatura

from api.service import index_one


def clean_extract(url: str) -> Optional[str]:
    html = trafilatura.fetch_url(url)
    if not html:
        return None
    text = trafilatura.extract(
        html,
        include_images=False,
        include_tables=False,
    )
    return text


def ingest_feed(url: str, limit: int = 20, lang: Optional[str] = None) -> int:
    """Descarga un feed RSS, extrae y indexa hasta `limit` artículos."""
    f = feedparser.parse(url)
    count = 0
    for e in f.entries[:limit]:
        article_url = getattr(e, "link", None)
        if not article_url:
            continue

        content = clean_extract(article_url)
        if not content:
            continue

        doc = {
            "title": getattr(e, "title", article_url),
            "url": article_url,
            "source": f.feed.get("title", "unknown"),
            "content": content,
            "language": lang or "es",
        }
        index_one(doc)
        count += 1
    return count
