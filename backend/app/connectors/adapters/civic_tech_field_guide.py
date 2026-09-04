"""
Civic Tech Field Guide connector — real, live JSON REST API, no key required.

Civic Tech Field Guide (https://civictech.guide/) is a community-maintained
directory of 8,000+ civic tech projects, tools, organizations, events, and
resources (Airtable-backed under the hood — every record carries an
``airtable_id``). It publishes a public "Build" developer portal at
https://civictech.guide/build documenting a first-party REST API and an MCP
server, both explicitly offered for free, self-serve, unauthenticated use
("no key required for basic search"), with the underlying dataset licensed
CC BY 4.0 (reuse, including commercial, permitted with attribution).

Endpoint used:
    GET https://civictech.guide/api/v1/projects/search

Verified live on 2026-09-04 via:
    curl "https://civictech.guide/api/v1/projects/search?limit=3&sort=newest"
which returned HTTP 200 with a real, current ``date:`` response header of
"Fri, 04 Sep 2026" and items with ``created_at`` timestamps of
2026-09-04T03:37:32Z / 2026-09-03T.../2026-09-02T... (i.e. items added to the
directory within the last two days), each fully populated with title, url,
description, categories, tags, location, and a nested ``raw_data`` object of
Airtable-native fields. Response envelope confirmed as
``{"data": [...], "meta": {"total": <int>}}``.

Also confirmed live:
  - No API key/Authorization header of any kind is sent or required; a bare
    GET succeeds (``ratelimit-limit: 300`` / ``ratelimit-remaining`` response
    headers show a generous public rate limit, not an auth gate).
  - ``limit`` is capped server-side at 100 per page (requesting 9999 silently
    returns 100 items, not an error).
  - ``sort`` only accepts ``relevance`` or ``newest`` — any other value
    (e.g. ``created_at``) returns HTTP 400 "Unknown sort: ... Use relevance
    or newest." We use ``sort=newest`` so repeated fetches surface freshly
    added entries first.
  - ``page`` is accepted for pagination (confirmed page=2 returns a
    different result set than page=1).
  - Every sampled item (100-item batch fetched during verification) had a
    non-empty top-level ``url`` field pointing at the project's own public
    site — used directly as this adapter's ``url``.
  - robots.txt for civictech.guide is "Allow: /" for all user agents, and in
    any case this is a documented first-party JSON API, not a scrape.

This source is fundamentally a directory of *existing* civic tech projects
and organizations rather than raw problem complaints/requests, so unlike
e.g. the CFPB or Reddit adapters it does not itself surface a distinct
"problem_frequency", "existing_solutions", "pricing_estimate", or
"problem_author" signal for the problem space a listed project operates in
— those are left as None for the downstream AI enrichment step to fill in,
per the shared adapter contract. Each listing's own title/description
(what civic problem the project exists to address) is the useful raw
material we extract here.

Docs referenced: https://civictech.guide/build and
https://civictech.guide/build#api (developer portal, human-readable; no
machine-readable OpenAPI spec was published there as of this writing).
"""

from __future__ import annotations

from typing import Any

from app.connectors.clients.api_client import get_json
from app.connectors.common import build_raw_data, stable_id, truncate_title

API_URL = "https://civictech.guide/api/v1/projects/search"
SOURCE_KEY = "civic-tech-field-guide"

DEFAULT_LIMIT = 20
MAX_PAGE_SIZE = 100  # server-enforced cap observed live; larger values are silently clamped


def _best_description(item: dict[str, Any]) -> str:
    """Prefer the longer write-up when the API's short and long fields differ."""
    long_desc = (item.get("longDescription") or "").strip()
    short_desc = (item.get("description") or item.get("introduction") or "").strip()
    if long_desc and long_desc != short_desc:
        return long_desc
    return short_desc or long_desc


def _map_item(item: dict[str, Any]) -> dict | None:
    """Map one Civic Tech Field Guide project/org/event record into the shared SourceItem shape."""
    natural_key = item.get("id") or item.get("airtable_id") or item.get("slug") or item.get("url")
    if not natural_key:
        return None

    raw_title = item.get("title") or item.get("name") or ""
    title = truncate_title(raw_title)
    if not title:
        return None

    url = item.get("url") or (item.get("socials") or {}).get("website")
    if not url:
        return None

    description = _best_description(item) or title

    categories = item.get("categories") or []
    category = categories[0] if categories else None

    location = item.get("location") or {}
    raw_data_native = item.get("raw_data") or {}

    return {
        "external_id": stable_id(SOURCE_KEY, str(natural_key)),
        "title": title,
        "description": description,
        "url": url,
        "problem_frequency": None,
        "existing_solutions": None,
        "pricing_estimate": None,
        "problem_author": None,
        "raw_data": build_raw_data(
            SOURCE_KEY,
            url,
            strategy="api",
            category=category,
            industry=None,
            score=None,
            extra={
                "slug": item.get("slug"),
                "airtable_id": item.get("airtable_id"),
                "status": item.get("status") or item.get("status_raw"),
                "categories": categories,
                "tags": item.get("tags") or [],
                "project_types": item.get("projectTypes"),
                "organization_type": item.get("organizationType"),
                "repository_url": item.get("repository_url"),
                "language": item.get("language"),
                "added": item.get("added"),
                "last_modified": item.get("lastModified"),
                "location": (
                    {"city": location.get("city"), "country": location.get("country")}
                    if (location.get("city") or location.get("country"))
                    else None
                ),
                "airtable_fields": raw_data_native,
            },
        ),
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch civic tech projects/organizations/events from the Civic Tech Field
    Guide's public, unauthenticated JSON REST API, newest-added first.

    Args:
        limit: Max number of problems to return. None fetches a reasonable
            default batch (DEFAULT_LIMIT). The API caps a single page at
            MAX_PAGE_SIZE regardless of the requested value.
    """
    effective_limit = limit if limit is not None and limit > 0 else DEFAULT_LIMIT
    page_size = min(max(effective_limit, 1), MAX_PAGE_SIZE)

    try:
        data = await get_json(
            API_URL,
            params={
                "limit": page_size,
                "sort": "newest",
            },
        )
    except Exception as e:
        raise Exception(f"Civic Tech Field Guide (public API) fetch failed: {e}") from e

    items = (data or {}).get("data") or []

    problems: list[dict] = []
    seen_ids: set[str] = set()
    for item in items:
        mapped = _map_item(item)
        if not mapped or mapped["external_id"] in seen_ids:
            continue
        seen_ids.add(mapped["external_id"])
        problems.append(mapped)
        if len(problems) >= effective_limit:
            break

    print(
        f"Civic Tech Field Guide: Extracted {len(problems)} problems "
        f"(page_size={page_size}, sort=newest, total_available={(data or {}).get('meta', {}).get('total')})"
    )
    return problems
