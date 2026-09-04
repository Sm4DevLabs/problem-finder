"""
Open Government Partnership connector — static CSV export, not the WordPress API.

OGP's WordPress REST API (https://www.opengovpartnership.org/wp-json/) is
locked to staff logins with no self-serve key, and the commitments
"Explorer" page (https://www.opengovpartnership.org/explorer/) is a
client-rendered app with nothing in its static HTML. But that Explorer app
itself loads its dataset from a plain, unauthenticated static file:

    https://www.opengovpartnership.org/explorer/data/latest_data/ogpirm_live_data.csv

Verified live on 2026-09-04: a bare GET (no auth, no cookies, no JS) returns
HTTP 200 and a 4.2MB CSV of 2,723 IRM (Independent Reporting Mechanism)
commitment rows across 67 countries, with columns including Country, Action
Plan Number, Theme, Comm No, Commitment Title, Full Text, Start Date, End
Date, Lead Institution, Supporting Institution(s).

Caveat: despite the "live_data" filename, sampled Start Date values only run
through ~2015 (Action Plan Numbers 1-2) — this is an archival IRM dataset
from OGP's earlier reporting cycles, not current-cycle commitments. Each
row's "Full Text" is still a genuine government reform commitment (a
real-world civic problem the lead institution committed to solve), so it's
useful raw material for this app, just not a live current-events feed. No
per-row URL exists in the CSV, so `url` falls back to the Explorer page
itself rather than fabricating a deep link.

No authentication or API key of any kind is required.
"""

from __future__ import annotations

import csv
import io

import httpx

from app.connectors.common import build_raw_data, stable_id, truncate_title

CSV_URL = "https://www.opengovpartnership.org/explorer/data/latest_data/ogpirm_live_data.csv"
EXPLORER_URL = "https://www.opengovpartnership.org/explorer/"
DEFAULT_USER_AGENT = "ProblemFinder/1.0 (+https://github.com/subh2312/problem-finder)"
DEFAULT_TIMEOUT = 30.0
SOURCE_KEY = "ogp"

DEFAULT_LIMIT = 20


async def _fetch_csv_rows() -> list[dict[str, str]]:
    headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "text/csv"}
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, trust_env=False, follow_redirects=True) as client:
        response = await client.get(CSV_URL, headers=headers)
        response.raise_for_status()
        text = response.text

    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def _clean(value: str | None) -> str | None:
    text = (value or "").strip()
    return text if text and text.lower() not in ("n/a", "na", "unclear", "not specified") else None


def _map_row(row: dict[str, str]) -> dict | None:
    country = _clean(row.get("Country"))
    commitment_title = _clean(row.get("Commitment Title")) or _clean(row.get("Short Title"))
    if not commitment_title:
        return None

    title = f"{commitment_title} — {country}" if country else commitment_title
    full_text = _clean(row.get("Full Text"))
    description = full_text or commitment_title

    action_plan = row.get("Action Plan Number") or ""
    comm_no = row.get("Comm No") or ""
    natural_key = f"{country}|{action_plan}|{comm_no}|{commitment_title}"

    lead_institution = _clean(row.get("Lead Institution"))
    theme = _clean(row.get("Theme"))

    return {
        "external_id": stable_id(SOURCE_KEY, natural_key),
        "title": truncate_title(title),
        "description": description,
        "url": EXPLORER_URL,
        "problem_frequency": None,
        "existing_solutions": None,
        "pricing_estimate": None,
        # The government body that committed to solving this problem is a
        # genuine, source-provided signal.
        "problem_author": lead_institution,
        "raw_data": build_raw_data(
            SOURCE_KEY,
            EXPLORER_URL,
            strategy="scrape",
            category=theme,
            industry=None,
            score=None,
            extra={
                "country": country,
                "action_plan_number": action_plan,
                "comm_no": comm_no,
                "start_date": row.get("Start Date"),
                "end_date": row.get("End Date"),
                "supporting_institutions": row.get("Supporting Institution(s)"),
                # Archival dataset — see module docstring.
                "data_recency": "archival (IRM cycles ~2011-2015 despite the live_data filename)",
            },
        ),
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch OGP IRM government commitments from the Explorer app's static CSV export.

    Args:
        limit: Max number of problems to return. None fetches a reasonable
            default batch (DEFAULT_LIMIT).

    Note:
        This is an archival dataset (see module docstring) — rows are real
        government reform commitments, but not current/live civic events.
    """
    effective_limit = limit if limit is not None and limit > 0 else DEFAULT_LIMIT

    try:
        rows = await _fetch_csv_rows()
    except Exception as e:
        raise Exception(f"Open Government Partnership (Explorer CSV export) fetch failed: {e}") from e

    problems: list[dict] = []
    seen_ids: set[str] = set()
    for row in rows:
        mapped = _map_row(row)
        if not mapped or mapped["external_id"] in seen_ids:
            continue
        seen_ids.add(mapped["external_id"])
        problems.append(mapped)
        if len(problems) >= effective_limit:
            break

    print(
        f"Open Government Partnership: Extracted {len(problems)} problems "
        f"(from {len(rows)} archival IRM commitment rows)"
    )
    return problems
