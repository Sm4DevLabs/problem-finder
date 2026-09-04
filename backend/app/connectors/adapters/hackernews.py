"""
Hacker News connector — Algolia HN Search API ("Ask HN" threads).

Hacker News itself is served by the read-only Firebase API
(https://hacker-news.firebaseio.com/v0/...), but that API only exposes raw
item/story IDs and requires N+1 requests to page through recent items with
no server-side filtering or full-text search. The community-run Algolia HN
Search API (https://hn.algolia.com/api) indexes the same data and adds
filtering/sorting for free, so it's the practical way to pull a themed batch
of items in one request. Both are public, unauthenticated, and free with no
API key or approval process.

Docs: https://hn.algolia.com/api
Endpoint used: https://hn.algolia.com/api/v1/search_by_date

We query ``tags=ask_hn`` because "Ask HN" (and "Tell HN") threads are where
the HN community explicitly raises problems, frustrations, and open
questions looking for solutions — a natural fit for a problem-finding feed,
unlike generic "Show HN"/link-share front-page stories.

Verified live on 2026-09-04 via:
    GET https://hn.algolia.com/api/v1/search_by_date?tags=ask_hn&hitsPerPage=8&numericFilters=points%3E3
which returned real, same-day "Ask HN" / "Tell HN" threads (e.g. objectID
49560168, "Ask HN: Why do many websites use a sign-in code instead of a
password?", created_at 2026-09-04T03:26:07Z) with fields: objectID, title,
story_text, author, points, num_comments, created_at, _tags. No `url` field
is present on self-post ("Ask HN") items, so the canonical HN discussion
page URL is constructed from objectID.

No authentication required.
"""

from __future__ import annotations

from typing import Any

from app.connectors.clients.api_client import get_json
from app.connectors.common import build_raw_data, stable_id, truncate_title

ALGOLIA_SEARCH_BY_DATE_URL = "https://hn.algolia.com/api/v1/search_by_date"
HN_ITEM_URL_TEMPLATE = "https://news.ycombinator.com/item?id={item_id}"
SOURCE_KEY = "hackernews"

DEFAULT_LIMIT = 20
# Filter out zero-engagement noise while still surfacing same-day threads.
MIN_POINTS = 3


def _map_item(item: dict[str, Any]) -> dict | None:
    """Map one Algolia HN hit into the shared SourceItem dict shape."""
    raw_title = item.get("title") or ""
    title = raw_title.strip()
    if not title:
        return None

    object_id = item.get("objectID") or item.get("story_id")
    if not object_id:
        return None
    object_id = str(object_id)

    url = HN_ITEM_URL_TEMPLATE.format(item_id=object_id)

    # Ask HN posts carry their body in `story_text` (HTML, often absent);
    # fall back to the title so description is never empty.
    story_text = (item.get("story_text") or "").strip()
    description = story_text or title

    return {
        "external_id": stable_id(SOURCE_KEY, object_id),
        "title": truncate_title(title),
        "description": description,
        "url": url,
        "problem_frequency": None,
        "existing_solutions": None,
        "pricing_estimate": None,
        # HN natively attributes each thread to the user who raised it.
        "problem_author": item.get("author"),
        "raw_data": build_raw_data(
            SOURCE_KEY,
            url,
            strategy="api",
            category="ask_hn",
            industry=None,
            score=item.get("points"),
            extra={
                "objectID": object_id,
                "num_comments": item.get("num_comments"),
                "created_at": item.get("created_at"),
                "tags": item.get("_tags"),
            },
        ),
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch recent "Ask HN" problem/discussion threads via the Algolia HN Search API.

    Args:
        limit: Max number of problems to return. None fetches a reasonable
            default batch (DEFAULT_LIMIT).
    """
    effective_limit = limit if limit is not None and limit > 0 else DEFAULT_LIMIT
    # Over-fetch a bit since some hits get filtered out (blank titles, dupes).
    hits_per_page = min(max(effective_limit * 2, 20), 100)

    try:
        data = await get_json(
            ALGOLIA_SEARCH_BY_DATE_URL,
            params={
                "tags": "ask_hn",
                "hitsPerPage": hits_per_page,
                "numericFilters": f"points>{MIN_POINTS}",
            },
        )
    except Exception as e:
        raise Exception(f"Hacker News (Algolia HN Search API) fetch failed: {e}") from e

    problems: list[dict] = []
    seen_ids: set[str] = set()
    for item in data.get("hits") or []:
        mapped = _map_item(item)
        if not mapped or mapped["external_id"] in seen_ids:
            continue
        seen_ids.add(mapped["external_id"])
        problems.append(mapped)
        if len(problems) >= effective_limit:
            break

    print(
        f"Hacker News: Extracted {len(problems)} problems "
        f"(tag=ask_hn, min_points={MIN_POINTS}, hits_per_page={hits_per_page})"
    )
    return problems
