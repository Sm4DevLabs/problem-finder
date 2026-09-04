"""
DrivenData Competitions connector — HTML scrape of the public competitions listing.

DrivenData (https://www.drivendata.org/) hosts data-science competitions where
NGOs, government agencies, and companies post real-world prediction problems
(the "problem_author" for each item is the organization that hosts/sponsors it).

Verified 2026-09-04: DrivenData has no public JSON/REST API for competitions
(no documented endpoint, no `/api/` routes on the site, no OpenAPI/Swagger
docs). The `https://www.drivendata.org/competitions/` page is a server-rendered
Django/Wagtail template — a `curl` of the page returns the full competition
list embedded directly in the HTML (title, category, description, prize,
participant count, difficulty, and close date all live in each
`div.panel-container` card), not fetched client-side via XHR/fetch. This was
confirmed live by fetching the page and inspecting the raw response body.

`robots.txt` (https://www.drivendata.org/robots.txt) only disallows
`/accounts/`, `/competitions/search/`, and `/*/leaderboard_partial` — the
`/competitions/` listing page itself is allowed for crawling.

The shared Crawlviel client (app/connectors/clients/crawlviel_client.py) was
also tried against this URL. It only has CMS-aware adapters for platforms
like Tilda/Framer; against this Django-rendered page it falls back to a
generic "http" strategy that flattens every `<a>` tag on the page (nav links,
category-filter links, competition links) into one undifferentiated list and
mis-resolves relative URLs (observed doubled `/competitions/competitions/...`
paths). That output cannot be reliably mapped back to
title/description/category/prize per competition, so this adapter parses the
HTML directly with BeautifulSoup (already a project dependency) via plain
httpx, per the "truly source-specific" escape hatch — no JSON API exists here
for api_client.get_json, and Crawlviel does not have a real extractor for
this site.

No authentication or API key of any kind is required or possible; this is a
public listing page.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.connectors.common import build_raw_data, stable_id, truncate_title

BASE_URL = "https://www.drivendata.org"
COMPETITIONS_URL = f"{BASE_URL}/competitions/"
USER_AGENT = "ProblemFinder/1.0 (+https://github.com/subh2312/problem-finder)"
DEFAULT_TIMEOUT = 30.0
DEFAULT_LIMIT = 20


async def _fetch_html(url: str) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, trust_env=False, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.text


def _card_category(card: Any) -> str | None:
    """Read the category from the filter-link query param (more reliable than the
    visible label, which falls back to the generic word "Competition" for
    externally-hosted partner challenges with no assigned category)."""
    cat_a = card.select_one("a.text-category")
    if not cat_a:
        return None
    href = cat_a.get("href") or ""
    qs = parse_qs(urlparse(href).query)
    value = (qs.get("category") or [None])[0]
    if value:
        return value.strip()
    text = cat_a.get_text(strip=True)
    return text or None


def _card_description(card: Any) -> str | None:
    desc_p = card.select_one("div.row-description p")
    if not desc_p:
        return None
    # The paragraph's first text node is the human-written description; the rest
    # is nested hashtag links we don't want inline. Fall back to the full text
    # if the markup doesn't match that shape.
    first = desc_p.contents[0] if desc_p.contents else None
    text = str(first).strip() if first is not None else ""
    return text or (desc_p.get_text(" ", strip=True) or None)


def _card_difficulty(card: Any) -> str | None:
    for key in card.attrs:
        if key.startswith("data-difficulty_"):
            return key[len("data-difficulty_") :]
    return None


def _card_host(card: Any) -> str | None:
    img = card.select_one(".panel-logo img")
    if not img:
        return None
    alt = (img.get("alt") or "").strip()
    return re.sub(r"^Hosted by\s+", "", alt).strip() or None


def _card_joined(card: Any) -> int | None:
    span = card.select_one("div.text-muted span")
    if not span:
        return None
    digits = re.sub(r"[^\d]", "", span.get_text())
    return int(digits) if digits else None


def _card_prize(card: Any) -> str | None:
    strong = card.select_one("span.prize strong")
    return strong.get_text(strip=True) if strong else None


def _card_end_date(card: Any) -> tuple[str | None, str | None]:
    span = card.select_one("span.end-date")
    if not span:
        return None, None
    return span.get_text(strip=True) or None, span.get("title")


def _parse_cards(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    for card in soup.select("div.panel-container"):
        title_a = card.select_one("h3.panel-competition-title a")
        if not title_a:
            continue
        title = title_a.get_text(strip=True)
        if not title:
            continue
        href = (title_a.get("href") or "").strip()
        if not href:
            continue
        url = urljoin(BASE_URL + "/", href)

        classes = card.get("class") or []
        end_text, end_title = _card_end_date(card)

        items.append(
            {
                "title": title,
                "url": url,
                "category": _card_category(card),
                "description": _card_description(card),
                "difficulty": _card_difficulty(card),
                "host": _card_host(card),
                "joined": _card_joined(card),
                "prize": _card_prize(card),
                "end_date_text": end_text,
                "end_date_utc": end_title,
                "status": "active" if "active-comp" in classes else ("completed" if "completed-comp" in classes else None),
                "has_cash_prize": "prize-comp" in classes,
            }
        )
    return items


def _map_item(raw: dict[str, Any]) -> dict[str, Any] | None:
    title = truncate_title(raw["title"])
    if not title:
        return None
    url = raw["url"]
    description = raw.get("description") or title

    return {
        "external_id": stable_id("drivendata", url),
        "title": title,
        "description": description,
        "url": url,
        "problem_frequency": None,
        "existing_solutions": None,
        "pricing_estimate": None,
        # The hosting organization is the real-world entity posing the problem
        # the competition is built to solve — a genuine signal this source
        # provides directly, unlike frequency/solutions/pricing.
        "problem_author": raw.get("host"),
        "raw_data": build_raw_data(
            "drivendata",
            url,
            strategy="scrape",
            category=raw.get("category"),
            industry=None,
            score=None,
            extra={
                "difficulty": raw.get("difficulty"),
                "status": raw.get("status"),
                "has_cash_prize": raw.get("has_cash_prize"),
                "prize": raw.get("prize"),
                "participants_joined": raw.get("joined"),
                "end_date_text": raw.get("end_date_text"),
                "end_date_utc": raw.get("end_date_utc"),
                # Named "hosting_org", not "host" — build_raw_data already
                # sets raw_data["host"] from the URL's network location;
                # reusing that key here would silently overwrite it.
                "hosting_org": raw.get("host"),
            },
        ),
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch DrivenData competitions by scraping the public competitions listing page.

    Args:
        limit: Max number of problems to return. None fetches a default batch
            (~20). The listing page returns active competitions/benchmarks
            first, then completed ones, so a small limit naturally favors
            currently-open challenges.
    """
    try:
        html = await _fetch_html(COMPETITIONS_URL)
    except Exception as e:
        raise Exception(f"DrivenData competitions page fetch failed: {e}") from e

    raw_items = _parse_cards(html)
    if not raw_items:
        raise Exception(
            "DrivenData scrape returned zero competition cards — the page markup "
            "likely changed (expected div.panel-container cards with a "
            "h3.panel-competition-title > a inside each) and the scraper needs updating."
        )

    effective_limit = limit if limit is not None else DEFAULT_LIMIT

    problems: list[dict] = []
    for raw in raw_items:
        mapped = _map_item(raw)
        if mapped:
            problems.append(mapped)
        if effective_limit is not None and len(problems) >= effective_limit:
            break

    print(f"DrivenData: Extracted {len(problems)} problems (scraped {len(raw_items)} cards from {COMPETITIONS_URL})")
    return problems
