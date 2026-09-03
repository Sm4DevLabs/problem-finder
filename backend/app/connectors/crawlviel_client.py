"""Shared Crawlviel API client for CMS-aware extraction."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_TIMEOUT = 180.0
DEFAULT_API_URL = "https://crawlviel-api.sm4devlabs.dpdns.org"


def _api_url() -> str:
    return os.getenv("CRAWLVIEL_API_URL", DEFAULT_API_URL).rstrip("/")


def _stable_id(prefix: str, key: str) -> str:
    digest = hashlib.sha256(key.strip().encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def _item_url(item: dict[str, Any]) -> str | None:
    for key in ("url", "link", "href"):
        val = item.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    return None


def _item_title(item: dict[str, Any]) -> str | None:
    for key in ("title", "name", "headline"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _item_text(item: dict[str, Any]) -> str | None:
    for key in ("text", "description", "body", "content", "summary"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = _item_url(item)
        title = _item_title(item)
        key = (url or "").lower() or (title or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


async def scrape_extract_all(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """
    Call Crawlviel POST /v1/scrape with extract_all=true (sync).

    Returns the Crawlviel `data` object: {url, strategy, total, items}.
    """
    api = _api_url()
    # trust_env=False: corporate HTTP(S)_PROXY often 403s public Crawlviel hosts
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        response = await client.post(
            f"{api}/v1/scrape",
            json={"url": url, "extract_all": True, "format": "json", "cache": True, "async": False},
        )
        response.raise_for_status()
        payload = response.json()

    if not payload.get("ok"):
        raise RuntimeError(f"Crawlviel scrape failed for {url}: {payload}")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected Crawlviel response for {url}: {payload}")

    items = data.get("items") or []
    if not isinstance(items, list):
        items = []
    data["items"] = _dedupe_items(items)
    data["total"] = len(data["items"])
    return data


def map_cms_item(
    item: dict[str, Any],
    *,
    source_key: str,
    id_prefix: str,
    fallback_url: str,
) -> dict[str, Any] | None:
    """Map a Crawlviel CMS item into problem-finder SourceItem fields."""
    title = _item_title(item)
    if not title:
        return None

    item_url = _item_url(item)
    url = item_url or fallback_url
    text = _item_text(item) or title
    category = item.get("category") or item.get("industry")
    score = item.get("score")

    # Analytical fields (frequency / solutions / pricing) are left empty here and
    # filled downstream by the enrichment service (AI) when the source does not
    # provide them. The raw CMS score is kept in raw_data, not shown as frequency.
    # Prefer per-item URL for IDs; Framer CMS often lacks detail URLs — fall back to title.
    return {
        "external_id": _stable_id(id_prefix, item_url or title),
        "title": title[:500],
        "description": text,
        "url": url,
        "problem_frequency": None,
        "existing_solutions": None,
        "pricing_estimate": None,
        "problem_author": None,
        "raw_data": {
            "source": source_key,
            "strategy": "crawlviel",
            "category": category,
            "industry": item.get("industry"),
            "score": score,
            "cms_item": {
                k: item.get(k)
                for k in ("title", "url", "category", "industry", "score")
                if item.get(k) is not None
            },
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "host": urlparse(url).netloc,
        },
    }


