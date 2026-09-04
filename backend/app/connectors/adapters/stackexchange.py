"""
Stack Exchange adapter — Stack Exchange API v2.3 (public REST API).

Docs: https://api.stackexchange.com/docs/questions

Live-verified 2026-09-04 via:

    GET https://api.stackexchange.com/2.3/questions/unanswered
        ?order=desc&sort=creation&site=softwarerecs&filter=withbody&pagesize=3

...returned real, current questions with creation_date timestamps resolving
to 2026-09-04 UTC (e.g. question_id 95563, "Database front-end/layout that
supports list view with 2 (or more) lines per entry", asked by a real user
that same day). Confirmed with a live curl request, not documentation alone.

Auth: NONE required. api.stackexchange.com/2.3 accepts fully anonymous,
unauthenticated GET requests with an IP-based quota of 300 requests/day.
Optionally, a free self-serve "app key" (instant registration, no approval
queue, at https://stackapps.com/apps/oauth/register) raises the quota to
10,000 requests/day/key. This adapter reads that optional key from the
STACKEXCHANGE_KEY env var (via python-dotenv) when present, but fetch()
works correctly with zero configuration.

Default site: softwarerecs.stackexchange.com ("Software Recommendations").
Every question on that site is, by construction, a person describing a
problem and asking "is there a tool/app/service that solves this?" — an
unusually direct, structured feed of real, dated problem statements that
often already states what the asker tried and why it fell short. This
adapter pulls *unanswered* questions specifically, since those are problems
the community has not yet pointed to an existing solution for. The target
site is overridable via the STACKEXCHANGE_SITE env var (any valid Stack
Exchange site slug, e.g. "stackoverflow", "ux", "webmasters", "askubuntu").
"""

from __future__ import annotations

import os

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from app.connectors.clients.api_client import get_json
from app.connectors.common import build_raw_data, stable_id, truncate_title

load_dotenv()

API_BASE = "https://api.stackexchange.com/2.3"
DEFAULT_SITE = os.getenv("STACKEXCHANGE_SITE", "softwarerecs")
API_KEY = os.getenv("STACKEXCHANGE_KEY")  # optional; raises daily quota, never required

_DEFAULT_LIMIT = 20
_MAX_PAGE_SIZE = 100  # Stack Exchange API hard cap on pagesize


def _html_to_text(html: str | None) -> str:
    """Strip Stack Exchange's HTML-formatted title/body down to plain text."""
    if not html:
        return ""
    text = BeautifulSoup(html, "html.parser").get_text(separator=" ")
    return " ".join(text.split())


def _map_question(item: dict, site: str) -> dict | None:
    title = _html_to_text(item.get("title")).strip()
    if not title:
        return None

    question_id = item.get("question_id")
    url = item.get("link") or f"https://{site}.stackexchange.com/questions/{question_id}"
    natural_key = str(question_id) if question_id is not None else url

    description = _html_to_text(item.get("body")) or title
    tags = item.get("tags") or []
    category = tags[0] if tags else None
    author = ((item.get("owner") or {}).get("display_name") or "").strip() or None

    return {
        "external_id": stable_id("stackexchange", natural_key),
        "title": truncate_title(title),
        "description": description,
        "url": url,
        "problem_frequency": None,
        "existing_solutions": None,
        "pricing_estimate": None,
        "problem_author": author,
        "raw_data": build_raw_data(
            "stackexchange",
            url,
            strategy="api",
            category=category,
            industry=None,
            score=item.get("score"),
            extra={
                "site": site,
                "question_id": question_id,
                "tags": tags,
                "answer_count": item.get("answer_count"),
                "view_count": item.get("view_count"),
                "is_answered": item.get("is_answered"),
                "creation_date": item.get("creation_date"),
            },
        ),
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch recent unanswered Stack Exchange questions as candidate problems.

    Args:
        limit: Max problems to return. None fetches a default batch (~20).

    Returns:
        List of problem dicts matching the shared connector contract.
    """
    page_size = min(max(limit or _DEFAULT_LIMIT, 1), _MAX_PAGE_SIZE)

    params: dict[str, object] = {
        "order": "desc",
        "sort": "creation",
        "site": DEFAULT_SITE,
        "filter": "withbody",
        "pagesize": page_size,
    }
    if API_KEY:
        params["key"] = API_KEY

    try:
        data = await get_json(f"{API_BASE}/questions/unanswered", params=params)
    except Exception as e:
        raise Exception(f"Stack Exchange fetch failed (site={DEFAULT_SITE}): {e}") from e

    items = (data or {}).get("items") or []
    problems: list[dict] = []
    for item in items:
        mapped = _map_question(item, DEFAULT_SITE)
        if mapped:
            problems.append(mapped)
        if limit is not None and len(problems) >= limit:
            break

    return problems
