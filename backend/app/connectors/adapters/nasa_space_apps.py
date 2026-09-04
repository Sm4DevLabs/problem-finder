"""
NASA Space Apps Challenge connector — public GraphQL API.

NASA Space Apps Challenge (https://www.spaceappschallenge.org/) is NASA's annual
global hackathon. Its "challenges" (real-world problem statements NASA and
partner agencies pose to participants each year, spanning many past events) are
served client-side by an unauthenticated, public Apollo GraphQL API at
``https://api.spaceappschallenge.org/graphql``.

There is no published API doc page for this endpoint; it is the same API the
public website itself calls to render https://www.spaceappschallenge.org/<year>/challenges/.
The exact `query Challenges(...)` shape and its `CoreChallengeFields` /
`ICategoryFields` / `ExpandedPageMetaFields` fragments used below were recovered
by inspecting the site's public Next.js JS bundles (no login, no dev tools
session, no private schema needed) and confirmed live on 2026-09-04 with a
plain POST request — e.g.::

    curl -s -X POST https://api.spaceappschallenge.org/graphql \\
      -H "Content-Type: application/json" \\
      -d '{"query":"query Challenges($first:Int!){challenges(first:$first){totalCount edges{node{id title excerpt}}}}","variables":{"first":3}}'

which returned real challenge data (``totalCount": 73`` live challenges spanning
the 2023 and 2025 events at the time of writing). Introspection is disabled on
the server, so the query below only uses fields verified via the JS bundle and
a live test call — no guessed/hallucinated fields.

No API key, token, or authentication of any kind is required; the endpoint is
public and used by anonymous visitors to the website itself. robots.txt on
``www.spaceappschallenge.org`` disallows ``/api/`` (a different, same-site
relative path — not this cross-host GraphQL API), and ``api.spaceappschallenge.org``
has no robots.txt of its own (404).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.connectors.common import build_raw_data, stable_id, truncate_title

GRAPHQL_URL = "https://api.spaceappschallenge.org/graphql"
SITE_URL = "https://www.spaceappschallenge.org"
DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = "ProblemFinder/1.0 (+https://github.com/subh2312/problem-finder)"
DEFAULT_LIMIT = 20
_MAX_PAGE_SIZE = 50
_MAX_PAGES = 10  # safety cap so a bad `limit` can't spin forever

# Recovered verbatim (field selection) from the site's own Next.js bundle —
# see module docstring. `event`, `skills`, `categories`, and `meta` all come
# back from a real anonymous request; nothing here is guessed.
_CHALLENGES_QUERY = """
query Challenges($first: Int!, $after: String) {
  challenges(first: $first, after: $after) {
    totalCount
    edges {
      cursor
      node {
        id
        title
        excerpt
        event
        skills
        meta {
          slug
          relativeUrl
          live
          firstPublishedAt
          lastPublishedAt
        }
        categories {
          name
          slug
          description
        }
        featuredImage {
          rendition {
            url
            fullUrl
          }
        }
      }
    }
    pageInfo {
      startCursor
      endCursor
      hasNextPage
      hasPreviousPage
    }
  }
}
"""


async def _query_challenges(*, first: int, after: str | None) -> dict[str, Any]:
    """POST one page of the Challenges GraphQL query. No auth headers needed."""
    headers = {"User-Agent": DEFAULT_USER_AGENT, "Content-Type": "application/json"}
    body = {"query": _CHALLENGES_QUERY, "variables": {"first": first, "after": after}}
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, trust_env=False) as client:
        response = await client.post(GRAPHQL_URL, json=body, headers=headers)
        response.raise_for_status()
        payload = response.json()

    if payload.get("errors"):
        raise RuntimeError(f"NASA Space Apps GraphQL errors: {payload['errors']}")
    return payload.get("data") or {}


def _map_node(node: dict[str, Any]) -> dict[str, Any] | None:
    title = (node.get("title") or "").strip()
    if not title:
        return None

    meta = node.get("meta") or {}
    relative_url = meta.get("relativeUrl") or ""
    url = f"{SITE_URL}{relative_url}" if relative_url else SITE_URL

    description = (node.get("excerpt") or "").strip() or title
    categories = [c.get("name") for c in (node.get("categories") or []) if c.get("name")]
    category = categories[0] if categories else None
    native_key = node.get("id") or relative_url or title
    image = ((node.get("featuredImage") or {}).get("rendition") or {}).get("fullUrl")

    return {
        "external_id": stable_id("nasa-space-apps", native_key),
        "title": truncate_title(title),
        "description": description,
        "url": url,
        "problem_frequency": None,
        "existing_solutions": None,
        "pricing_estimate": None,
        "problem_author": None,
        "raw_data": build_raw_data(
            "nasa-space-apps",
            url,
            strategy="api",
            category=category,
            industry=None,
            score=None,
            extra={
                "challenge_id": node.get("id"),
                "categories": categories,
                "skills": node.get("skills") or [],
                "event": node.get("event"),
                "slug": meta.get("slug"),
                "live": meta.get("live"),
                "first_published_at": meta.get("firstPublishedAt"),
                "last_published_at": meta.get("lastPublishedAt"),
                "featured_image": image,
            },
        ),
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch real challenge problem statements from the NASA Space Apps Challenge
    public GraphQL API (no authentication required).

    Args:
        limit: Optional max items to return. None fetches a reasonable default
            batch (~20). Pages through the API's cursor pagination as needed.
    """
    target = limit if limit is not None else DEFAULT_LIMIT
    if target <= 0:
        return []
    page_size = min(target, _MAX_PAGE_SIZE)

    problems: list[dict] = []
    seen_ids: set[str] = set()
    after: str | None = None
    total_count: int | None = None

    for _ in range(_MAX_PAGES):
        try:
            data = await _query_challenges(first=page_size, after=after)
        except Exception as e:
            raise Exception(f"NASA Space Apps Challenge fetch failed: {e}") from e

        challenges = data.get("challenges") or {}
        if total_count is None:
            total_count = challenges.get("totalCount")

        for edge in challenges.get("edges") or []:
            node = (edge or {}).get("node") or {}
            mapped = _map_node(node)
            if mapped and mapped["external_id"] not in seen_ids:
                seen_ids.add(mapped["external_id"])
                problems.append(mapped)
            if len(problems) >= target:
                break

        if len(problems) >= target:
            break

        page_info = challenges.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            break

    print(
        f"NASA Space Apps Challenge: Extracted {len(problems)} problems "
        f"(totalCount={total_count})"
    )
    return problems
