"""
CFPB Consumer Complaint Database connector — real, unredacted-by-us consumer
financial complaints, straight from the U.S. Consumer Financial Protection
Bureau's public Elasticsearch-backed search API.

The CFPB explicitly invites third-party developers to "build your own tools
using our API to access the Consumer Complaint Database"
(https://cfpb.github.io/api/ccdb/). No API key, account, or approval process
of any kind is required — it is a fully open, unauthenticated government API.
robots.txt for consumerfinance.gov does not restrict this path.

Endpoint used:
    GET https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/

Verified live on 2026-09-04 via:
    GET .../api/v1/?size=5&no_aggs=true&sort=created_date_desc&has_narrative=true
which returned real, same-week complaints (e.g. complaint_id 25206546,
date_received 2026-09-03T...) each with a populated free-text
``complaint_what_happened`` narrative such as: "They claim on my credit
report that this item is charged off, however I make timely payments on
t[...]". Confirmed response shape: top-level keys took/timed_out/_shards/
hits/_meta (no "aggregations" key when no_aggs=true is passed), with each
``hits.hits[].source`` containing: complaint_id, product, sub_product,
issue, sub_issue, company, company_response, company_public_response,
state, zip_code, date_received, date_sent_to_company, submitted_via, tags,
timely, has_narrative, complaint_what_happened.

We filter to ``has_narrative=true`` because most complaints in the raw feed
have an empty ``complaint_what_happened`` (consumer declined to share a
narrative, or it's not yet published); only narrative complaints read as
genuine, usable "problem" write-ups for this app.

Consumer identities are never included by CFPB (complaints are published
anonymized, with narratives containing CFPB's own "XX/XX/XXXX" / "XXXX"
style PII scrubbing already applied), so ``problem_author`` is always None
here — that's a genuine property of the source, not a gap we're leaving for
enrichment.

There is no confirmed stable public deep-link to a single complaint (the
CFPB search UI at .../consumer-complaints/search/ is a client-side-rendered
React app; we could not verify from a non-JS fetch that a
``?complaint_id=`` query param opens that specific record). To avoid
fabricating a URL we haven't confirmed resolves to the specific complaint,
``url`` points at the live public search page filtered by the same
complaint_id query param CFPB's own API accepts as a filter field — this
page reliably loads (confirmed 200 OK) and, at minimum, lets a human search
for that exact complaint from there even if the SPA doesn't auto-scope to
it.
"""

from __future__ import annotations

from typing import Any

from app.connectors.clients.api_client import get_json
from app.connectors.common import build_raw_data, stable_id, truncate_title

API_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
SEARCH_PAGE_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/"
SOURCE_KEY = "cfpb"

DEFAULT_LIMIT = 20


def _build_title(source: dict[str, Any]) -> str:
    issue = (source.get("issue") or "").strip()
    product = (source.get("product") or "").strip()
    sub_issue = (source.get("sub_issue") or "").strip()

    if issue and product:
        title = f"{issue} — {product}"
    elif issue:
        title = issue
    elif product:
        title = product
    else:
        title = sub_issue
    return title.strip()


def _map_hit(hit: dict[str, Any]) -> dict | None:
    """Map one CFPB complaint hit into the shared SourceItem dict shape."""
    source = hit.get("_source") or {}

    complaint_id = source.get("complaint_id")
    if not complaint_id:
        return None
    complaint_id = str(complaint_id)

    title = truncate_title(_build_title(source))
    if not title:
        return None

    narrative = (source.get("complaint_what_happened") or "").strip()
    if not narrative:
        # We filtered on has_narrative=true, but be defensive anyway —
        # a title-only complaint isn't a useful "problem" write-up.
        return None

    url = f"{SEARCH_PAGE_URL}?complaint_id={complaint_id}"

    return {
        "external_id": stable_id(SOURCE_KEY, complaint_id),
        "title": title,
        "description": narrative,
        "url": url,
        "problem_frequency": None,
        "existing_solutions": None,
        "pricing_estimate": None,
        # CFPB publishes complaints anonymized — there is no consumer
        # identity in the data, so this is genuinely unknown, not a gap.
        "problem_author": None,
        "raw_data": build_raw_data(
            SOURCE_KEY,
            url,
            strategy="api",
            category=source.get("product"),
            industry=None,
            score=None,
            extra={
                "complaint_id": complaint_id,
                "sub_product": source.get("sub_product"),
                "issue": source.get("issue"),
                "sub_issue": source.get("sub_issue"),
                "company": source.get("company"),
                "company_response": source.get("company_response"),
                "state": source.get("state"),
                "date_received": source.get("date_received"),
                "date_sent_to_company": source.get("date_sent_to_company"),
                "submitted_via": source.get("submitted_via"),
                "tags": source.get("tags"),
                "timely": source.get("timely"),
            },
        ),
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch recent, narrative-bearing consumer complaints from the CFPB
    Consumer Complaint Database public API.

    Args:
        limit: Max number of problems to return. None fetches a reasonable
            default batch (DEFAULT_LIMIT).
    """
    effective_limit = limit if limit is not None and limit > 0 else DEFAULT_LIMIT
    # Over-fetch a bit since some hits get filtered out (missing narrative,
    # blank title, or duplicate complaint ids across pages).
    page_size = min(max(effective_limit * 2, 20), 100)

    try:
        data = await get_json(
            API_URL,
            params={
                "size": page_size,
                "no_aggs": "true",
                "no_highlight": "true",
                "sort": "created_date_desc",
                "has_narrative": "true",
            },
        )
    except Exception as e:
        raise Exception(
            f"CFPB Consumer Complaint Database (public search API) fetch failed: {e}"
        ) from e

    hits = ((data or {}).get("hits") or {}).get("hits") or []

    problems: list[dict] = []
    seen_ids: set[str] = set()
    for hit in hits:
        mapped = _map_hit(hit)
        if not mapped or mapped["external_id"] in seen_ids:
            continue
        seen_ids.add(mapped["external_id"])
        problems.append(mapped)
        if len(problems) >= effective_limit:
            break

    print(
        f"CFPB Consumer Complaint Database: Extracted {len(problems)} problems "
        f"(page_size={page_size}, has_narrative=true, sort=created_date_desc)"
    )
    return problems
