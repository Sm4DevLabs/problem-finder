"""
NYC 311 Service Requests connector — Socrata SODA API (public, unauthenticated).

NYC Open Data publishes the full "311 Service Requests from 2010 to
Present" dataset via Socrata's SODA API. Dataset landing page:

    https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9

JSON resource endpoint (dataset id ``erm2-nwe9``):

    https://data.cityofnewyork.us/resource/erm2-nwe9.json

SODA query language (SoQL) reference: https://dev.socrata.com/docs/queries/

Verified live on 2026-09-04 by fetching real data against the endpoint above:

  - Plain GET (no params) returned current records, e.g. unique_key
    "70263450", created_date "2026-09-02T02:50:35.000", complaint_type
    "Street Condition" / descriptor "Pothole" in Brooklyn.
  - An aggregate SoQL query (``$select`` with ``count(unique_key)``,
    ``$group``, ``$where created_date >= ...``, ``$order ... DESC``)
    returned live grouped counts, e.g. complaint_type "Noise -
    Street/Sidewalk" / descriptor "Loud Music/Party" with 17,357 reports
    in the prior ~30 days.
  - A field-equality filter (``?complaint_type=...&descriptor=...``)
    returned matching individual records, confirming per-item deep
    links resolve to real filtered data.

No API key, login, or paid plan is required to call this endpoint —
it's a plain, unauthenticated GET, and NYC Open Data's Terms of Use
(https://www1.nyc.gov/home/terms-of-use.page) explicitly grant reuse of
this open data. An optional, free, self-serve Socrata "app token" can be
requested at https://data.cityofnewyork.us/profile/edit/developer_settings
to raise the (generous, anonymous-friendly) throttling limits, but it is
not required for the modest, single-request-per-fetch volume this
adapter makes. If present, the token is read from the environment (via
python-dotenv, consistent with the rest of this codebase) and sent as
an ``X-App-Token`` header; if absent, requests proceed unauthenticated.

Design note — why this adapter aggregates instead of returning raw
complaints: a single 311 report ("pothole on Fillmore Avenue") is a
one-off incident, not a reusable "problem" signal a founder could build
a product around. Instead, this adapter runs one SoQL aggregate query
that groups all complaints from the trailing ``_WINDOW_DAYS`` window by
(complaint_type, descriptor, agency) and ranks them by report volume.
Each returned "problem" is therefore a *recurring civic pain point*
(e.g. "Loud Music/Party — Noise - Street/Sidewalk", 17k+ reports/30
days), with that live report count surfaced verbatim as
``problem_frequency`` — one of the rare cases where the source itself
directly provides that exact signal, so it is not left for downstream
AI enrichment to guess.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from dotenv import load_dotenv

from app.connectors.clients.api_client import get_json
from app.connectors.common import build_raw_data, stable_id, truncate_title

load_dotenv()

BASE_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
DEFAULT_LIMIT = 20
_WINDOW_DAYS = 30  # trailing window used to rank "currently trending" civic complaints


def _app_token_headers() -> dict[str, str]:
    """Optional, free, self-serve Socrata app token for higher rate limits.

    Not required for this adapter's low request volume (one aggregate
    query per fetch). See module docstring for how a user would obtain one.
    """
    token = (os.getenv("NYC_311_APP_TOKEN") or os.getenv("SOCRATA_APP_TOKEN") or "").strip()
    return {"X-App-Token": token} if token else {}


def _display_descriptor(descriptor: str | None) -> str | None:
    text = (descriptor or "").strip()
    if not text or text.upper() in ("N/A", "NA", "UNSPECIFIED"):
        return None
    return text


def _format_count(raw_count: object) -> tuple[int | None, str]:
    try:
        count_int = int(str(raw_count))
    except (TypeError, ValueError):
        return None, str(raw_count)
    return count_int, f"{count_int:,}"


def _map_row(row: dict) -> dict | None:
    complaint_type = (row.get("complaint_type") or "").strip()
    if not complaint_type:
        return None

    descriptor = _display_descriptor(row.get("descriptor"))
    agency = (row.get("agency") or "").strip() or None
    agency_name = (row.get("agency_name") or "").strip() or agency or "the responsible NYC agency"

    title = f"{descriptor} — {complaint_type}" if descriptor else complaint_type

    count_int, count_disp = _format_count(row.get("complaint_count"))

    if descriptor:
        subject_clause = f'for "{descriptor}" under the "{complaint_type}" category'
    else:
        subject_clause = f'under the "{complaint_type}" category'
    description = (
        f"New Yorkers filed {count_disp} NYC 311 complaints in the last {_WINDOW_DAYS} days "
        f"{subject_clause}, handled by {agency_name}. "
        f"Recurring volume at this scale points to a persistent civic pain point that "
        f"residents want resolved faster, tracked more transparently, or routed to the "
        f"right agency more easily."
    )

    problem_frequency = f"{count_disp} 311 complaints citywide in the last {_WINDOW_DAYS} days"

    natural_key = "|".join(
        part.strip().lower() for part in (complaint_type, descriptor or "", agency or "")
    )

    detail_params = {"complaint_type": complaint_type}
    if row.get("descriptor"):
        detail_params["descriptor"] = row["descriptor"]
    url = f"{BASE_URL}?{urlencode(detail_params)}"

    return {
        "external_id": stable_id("nyc-311", natural_key),
        "title": truncate_title(title),
        "description": description,
        "url": url,
        "problem_frequency": problem_frequency,
        "existing_solutions": None,
        "pricing_estimate": None,
        "problem_author": None,
        "raw_data": build_raw_data(
            "nyc-311",
            url,
            strategy="api",
            category=complaint_type,
            industry=None,
            score=count_int,
            extra={
                "complaint_type": complaint_type,
                "descriptor": row.get("descriptor"),
                "agency": agency,
                "agency_name": row.get("agency_name"),
                "complaint_count": row.get("complaint_count"),
                "most_recent_report": row.get("most_recent"),
                "window_days": _WINDOW_DAYS,
                "dataset": "erm2-nwe9",
            },
        ),
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch the most-reported NYC 311 complaint patterns of the last 30 days.

    Runs a single SoQL aggregate query against NYC Open Data's public,
    unauthenticated "311 Service Requests" endpoint grouping complaints
    by (complaint_type, descriptor, agency) over a trailing 30-day
    window, ranked by report volume descending.

    Args:
        limit: Max problems to return. None => a default batch of ~20.

    Returns:
        List of problem dicts, one per recurring complaint pattern.
    """
    effective_limit = limit if limit is not None and limit > 0 else DEFAULT_LIMIT
    request_limit = min(effective_limit + 10, 200)  # small buffer for any filtered-out rows

    cutoff = datetime.now(timezone.utc) - timedelta(days=_WINDOW_DAYS)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")

    params = {
        "$select": (
            "complaint_type, descriptor, agency, agency_name, "
            "count(unique_key) AS complaint_count, "
            "max(created_date) AS most_recent"
        ),
        "$where": f"created_date >= '{cutoff_str}'",
        "$group": "complaint_type, descriptor, agency, agency_name",
        "$order": "complaint_count DESC",
        "$limit": request_limit,
    }

    try:
        rows = await get_json(BASE_URL, params=params, headers=_app_token_headers())
    except Exception as e:
        raise Exception(f"NYC 311 fetch failed: {e}") from e

    if not isinstance(rows, list):
        raise Exception(f"NYC 311 fetch failed: unexpected response shape: {type(rows)!r}")

    problems: list[dict] = []
    seen_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        mapped = _map_row(row)
        if mapped and mapped["external_id"] not in seen_ids:
            seen_ids.add(mapped["external_id"])
            problems.append(mapped)
        if len(problems) >= effective_limit:
            break

    print(
        f"NYC 311: Extracted {len(problems)} recurring complaint patterns "
        f"from the last {_WINDOW_DAYS} days"
    )
    return problems
