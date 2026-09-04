"""
Indie Hackers connector — Crawlviel scrape of the public "Ideas DB".

Verified 2026-09-04: indiehackers.com has no public/official API (no
`/api`, `/developers`, or documented REST surface exists — its footer only
links to Community / Products / Databases / FAQ / Terms). The site also
sits behind Cloudflare's managed-challenge bot protection, so a plain
`httpx`/`requests` GET (including a request for `/robots.txt` itself)
receives a JS "Just a moment..." challenge page instead of real content.

Real, current data IS reachable through the same shared Crawlviel scraping
service already used by ``problemhunt.py`` and ``_razorpay_crawlviel.py``
(``app.connectors.clients.crawlviel_client``), which was confirmed live
against:

    https://www.indiehackers.com/ideas

This "Ideas DB" page is a curated database of proven startup ideas —
each card names a real product, a one-line problem/opportunity
description, category tags, and the product's public MRR (e.g.
"$220K MRR"). That maps unusually well onto the SourceItem contract:
the idea sentence *is* the problem, and the named product/MRR are the
source's own natural "existing solution" and "pricing" signals, so
those two fields are populated here instead of left for AI enrichment.

Crawlviel's generic same-origin link extractor has a known quirk on this
page: it mis-resolves some relative hrefs, duplicating the `/ideas/`
path segment (e.g. ``.../ideas/ideas/<slug>-<id>``). This adapter works
around it by rebuilding the canonical URL from only the last path
segment, which reliably contains ``<slug>-<id>`` regardless of the
duplication bug.

Card text itself is also returned pre-flattened with no delimiter
between fields, e.g.::

    "Prerender.ioA hosted rendering service that makes JavaScript sites
     visible to crawlers.Developer ToolsTechnical SEOSaaS$220K MRR"

which is split back into (product name, idea sentence, tags, revenue)
via boundary regexes (verified against all ~116 items on the live page
with zero parse anomalies at the time of writing).

No credentials of any kind are required — Crawlviel itself needs no API
key here (only ``CRAWLVIEL_API_URL``, already set via .env for the other
crawlviel-backed adapters in this codebase).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.connectors.clients.crawlviel_client import scrape_extract_all
from app.connectors.common import build_raw_data, stable_id, truncate_title

IDEAS_DB_URL = "https://www.indiehackers.com/ideas"
DEFAULT_LIMIT = 20

# Idea-card detail URLs end in "<slug>-<20ish-char-id>"; nav/chrome links
# (Home, Sign in, Starting Up, ...) never carry this suffix, so it doubles
# as our "is this a real idea card" filter.
_ID_SUFFIX_RE = re.compile(r"-([A-Za-z0-9]{15,25})$")

# Revenue is always the trailing "$<amount><K|M|MM|B>?+? MRR" chunk.
_REVENUE_RE = re.compile(r"(\$[^$]*?MRR)\s*$")

# The idea sentence always starts with "A " / "An " glued directly onto the
# end of the product name (no separator was scraped between the two
# fields), so the first "A "/"An " preceded by an alnum or closing-paren
# character marks the name/description boundary.
_NAME_DESC_BOUNDARY_RE = re.compile(r"(?<=[a-zA-Z0-9)])(An |A )")

# The idea sentence is a single clause ending in ".", immediately glued to
# the (also delimiter-free) category tags that follow it.
_DESC_END_RE = re.compile(r"\.(?=[A-Z])")


def _canonical_url(raw_url: str) -> str | None:
    """Rebuild a clean detail URL from Crawlviel's (sometimes duplicated) path."""
    path = urlparse(raw_url).path.rstrip("/")
    if not path:
        return None
    last_segment = path.rsplit("/", 1)[-1]
    if not _ID_SUFFIX_RE.search(last_segment):
        return None
    return f"{IDEAS_DB_URL}/{last_segment}"


def _parse_card(raw_title: str) -> dict[str, str | None] | None:
    """Split a flattened Ideas DB card string into its component fields."""
    revenue_match = _REVENUE_RE.search(raw_title)
    revenue = revenue_match.group(1).strip() if revenue_match else None
    remainder = raw_title[: revenue_match.start()] if revenue_match else raw_title

    boundary = _NAME_DESC_BOUNDARY_RE.search(remainder)
    if not boundary:
        return None
    name = remainder[: boundary.start()].strip()
    desc_and_tags = remainder[boundary.start() :]
    if not name:
        return None

    end_match = _DESC_END_RE.search(desc_and_tags)
    if end_match:
        description = desc_and_tags[: end_match.end()].strip()
        tags_blob = desc_and_tags[end_match.end() :]
    else:
        description = desc_and_tags.strip()
        tags_blob = ""

    if not description:
        return None

    # Best-effort re-spacing of the glued-together tag chips for display;
    # not authoritative (adjacent all-caps acronyms like "SEO"+"SaaS" can
    # still merge), so it's kept as a free-form category string rather
    # than split into a list.
    tags = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", tags_blob).strip() or None

    return {"name": name, "description": description, "revenue": revenue, "tags": tags}


def _map_item(item: dict) -> dict | None:
    raw_url = item.get("url")
    if not isinstance(raw_url, str):
        return None
    url = _canonical_url(raw_url)
    if not url:
        return None

    raw_title = (item.get("title") or "").strip()
    if not raw_title:
        return None

    parsed = _parse_card(raw_title)
    if not parsed:
        return None

    native_id = url.rsplit("-", 1)[-1]
    title = truncate_title(parsed["description"])
    if not title:
        return None

    description = parsed["description"]
    if parsed["name"]:
        description = f"{description} Real-world example: {parsed['name']}."

    return {
        "external_id": stable_id("indie-hackers", native_id),
        "title": title,
        "description": description,
        "url": url,
        "problem_frequency": None,
        # The Ideas DB names an already-shipped product that implements
        # this exact idea — a genuine "existing solution" signal, not a
        # fabricated one.
        "existing_solutions": parsed["name"],
        # The card's public MRR figure is the source's own pricing signal.
        "pricing_estimate": parsed["revenue"],
        "problem_author": None,
        "raw_data": build_raw_data(
            "indie-hackers",
            url,
            strategy="scrape",
            category=parsed["tags"],
            industry=None,
            score=None,
            extra={
                "product_name": parsed["name"],
                "mrr": parsed["revenue"],
                "native_id": native_id,
                "raw_card_text": raw_title,
            },
        ),
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch problem/idea entries from the Indie Hackers "Ideas DB" via Crawlviel.

    Args:
        limit: Max items to return (None = a reasonable default batch of ~20).
    """
    effective_limit = limit if limit is not None else DEFAULT_LIMIT

    try:
        data = await scrape_extract_all(IDEAS_DB_URL)
    except Exception as e:
        raise Exception(f"Indie Hackers Crawlviel fetch failed: {e}") from e

    problems: list[dict] = []
    seen_ids: set[str] = set()
    for item in data.get("items") or []:
        mapped = _map_item(item)
        if not mapped or mapped["external_id"] in seen_ids:
            continue
        seen_ids.add(mapped["external_id"])
        problems.append(mapped)
        if effective_limit is not None and len(problems) >= effective_limit:
            break

    print(
        f"Indie Hackers: Extracted {len(problems)} problems "
        f"(strategy={data.get('strategy')}, crawlviel_total={data.get('total')})"
    )
    return problems
