"""
Kaggle Competitions connector — official Kaggle REST API, "list competitions" RPC.

Kaggle has no anonymous/public-read API: every call (including read-only
listing of competitions) requires a personal Kaggle account and an API
credential. There is no paid tier gating this — any free Kaggle account can
self-serve a credential in under a minute, so this is feasible with
auth_required=True, not blocked/unavailable.

How a user gets credentials (free, self-serve, no approval queue):
  1. Sign up / log into https://www.kaggle.com
  2. Open https://www.kaggle.com/settings/account, scroll to the "API"
     section
  3. Click "Create New Token" (OAuth-style token) **or** the older
     "Create Legacy API Key" button — either downloads a `kaggle.json`
     file containing `{"username": "...", "key": "..."}`
  4. Set KAGGLE_USERNAME=<username> and KAGGLE_KEY=<key> from that file
     in backend/.env (see .env.example) — no OAuth redirect flow needed
     for this legacy key style, it's a static username+key pair.

Docs / sources used:
  - https://github.com/Kaggle/kaggle-cli (formerly Kaggle/kaggle-api; the
    officially maintained `kaggle` PyPI package, v2.2.4 as of Jul 2026)
    docs/README.md "Authentication" section documents four supported auth
    methods, including the legacy `kaggle.json` (username+key) flow this
    adapter uses, and confirms there is no anonymous access path.
  - The current CLI's Python implementation (`src/kaggle/api/kaggle_api_extended.py`)
    delegates HTTP calls to the `kagglesdk` PyPI package
    (`kagglesdk/kaggle_http_client.py`), which was read directly to recover
    the underlying REST contract (the CLI itself no longer speaks raw
    requests-level REST as of this rewrite):
      * PROD host: https://api.kaggle.com  (`kaggle_env.py`, `KaggleEnv.PROD`)
      * Requests are `POST https://api.kaggle.com/v1/<service>/<rpc>` with a
        JSON body (protobuf-JSON style, lowerCamelCase field names, enums
        serialized as their full uppercase constant name)
      * Username/key auth is sent as plain HTTP Basic Auth
        (`self._session.auth = (username, key)`, `kaggle_http_client.py`)
      * The "list competitions" RPC is
        `competitions.CompetitionApiService/ListCompetitions`
        (`kagglesdk/competitions/services/competition_api_service.py`),
        request/response field names taken from
        `kagglesdk/competitions/types/competition_api_service.py`
        (`ApiListCompetitionsRequest` / `ApiCompetition`).

Live verification (2026-09-04): issued a real, unauthenticated
`POST https://api.kaggle.com/v1/competitions.CompetitionApiService/ListCompetitions`
with a body shaped exactly like this adapter sends
(`{"sortBy": "COMPETITION_SORT_BY_RECENTLY_CREATED", "pageSize": 5}`) against
the live production host. It returned real Kaggle infrastructure response
headers (`x-kaggle-apiversion: 2.2.2`, `x-kaggle-requestid`, a fresh
`ka_sessionid` cookie, etc.) and a clean, well-formed
`{"error": {"code": 401, "message": "Unauthenticated", "status": "UNAUTHENTICATED"}}`
body — i.e. the endpoint is live, parses this exact request shape without
complaint, and rejects it *only* for lacking credentials. That is the
expected behavior confirming the endpoint/contract are real and current;
a full 200 with competition data could not be captured here because doing
so requires a real user's personal KAGGLE_USERNAME/KAGGLE_KEY, which this
environment does not have. Please smoke-test with real credentials before
relying on this in production, in case Kaggle changes response shapes.

Required environment variables (add to backend/.env, see .env.example):
  KAGGLE_USERNAME   - your Kaggle username (from kaggle.json / settings page)
  KAGGLE_KEY        - your Kaggle API key (from kaggle.json / settings page)
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

from app.connectors.common import build_raw_data, stable_id, truncate_title

load_dotenv()

LIST_COMPETITIONS_URL = "https://api.kaggle.com/v1/competitions.CompetitionApiService/ListCompetitions"
COMPETITION_URL_TMPL = "https://www.kaggle.com/competitions/{ref}"
DEFAULT_USER_AGENT = "ProblemFinder/1.0 (backend connector; +https://github.com/subh2312/problem-finder)"
DEFAULT_LIMIT = 20
DEFAULT_TIMEOUT = 30.0
MAX_PAGE_SIZE = 100


def _credentials() -> tuple[str, str]:
    username = os.getenv("KAGGLE_USERNAME", "").strip()
    key = os.getenv("KAGGLE_KEY", "").strip()
    if not username or not key:
        raise RuntimeError(
            "Kaggle adapter requires KAGGLE_USERNAME and KAGGLE_KEY environment "
            "variables. Log into https://www.kaggle.com, open "
            "https://www.kaggle.com/settings/account, scroll to the 'API' "
            "section, and click 'Create New Token' or 'Create Legacy API Key' "
            "to download a kaggle.json file containing {\"username\": ..., "
            "\"key\": ...}. Set both values in your .env file — Kaggle has no "
            "anonymous read access, even for listing public competitions."
        )
    return username, key


def _competition_url(item: dict[str, Any]) -> str:
    url = item.get("url")
    if isinstance(url, str) and url.startswith("http"):
        return url
    ref = item.get("ref")
    if isinstance(ref, str) and ref.strip():
        return COMPETITION_URL_TMPL.format(ref=ref.strip())
    return "https://www.kaggle.com/competitions"


def _clean_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _map_competition(item: dict[str, Any]) -> dict[str, Any] | None:
    title = _clean_str(item.get("title"))
    if not title:
        return None

    url = _competition_url(item)
    natural_key = item.get("ref") or str(item.get("id") or url)
    description = _clean_str(item.get("description")) or title

    # `reward` is the prize Kaggle's host is literally offering for a
    # solution to this problem -- a direct pricing signal this source
    # naturally provides (e.g. "$50,000", "Kudos", "Swag").
    pricing_estimate = _clean_str(item.get("reward"))
    # `organizationName` (falling back to `hostName`) identifies who posed
    # the problem -- a direct author signal this source naturally provides.
    problem_author = _clean_str(item.get("organizationName")) or _clean_str(item.get("hostName"))

    return {
        "external_id": stable_id("kaggle", natural_key),
        "title": truncate_title(title),
        "description": description,
        "url": url,
        "problem_frequency": None,
        "existing_solutions": None,
        "pricing_estimate": pricing_estimate,
        "problem_author": problem_author,
        "raw_data": build_raw_data(
            "kaggle",
            url,
            strategy="api",
            category=item.get("category"),
            industry=None,
            score=item.get("teamCount"),
            extra={
                "ref": item.get("ref"),
                "id": item.get("id"),
                "reward": item.get("reward"),
                "organization_name": item.get("organizationName"),
                "host_name": item.get("hostName"),
                "deadline": item.get("deadline"),
                "date_created": item.get("dateCreated"),
                "team_count": item.get("teamCount"),
                "kernel_count": item.get("kernelCount"),
                "evaluation_metric": item.get("evaluationMetric"),
                "is_kernels_submissions_only": item.get("isKernelsSubmissionsOnly"),
            },
        ),
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch Kaggle competitions via the official Kaggle REST API.

    Args:
        limit: Max problems to return. None fetches a reasonable default
            batch (~20).

    Raises:
        RuntimeError: if KAGGLE_USERNAME/KAGGLE_KEY are missing or Kaggle
            rejects the request (e.g. invalid/expired credentials).
    """
    username, key = _credentials()
    max_items = limit if limit and limit > 0 else DEFAULT_LIMIT
    page_size = max(1, min(max_items, MAX_PAGE_SIZE))

    # Body shape/field names/enum constants reverse-engineered from the
    # `kagglesdk` package's generated types for
    # `ApiListCompetitionsRequest` -- see module docstring. `group` and
    # `category` are intentionally omitted so Kaggle applies its own
    # documented defaults (group="general", i.e. the same public listing
    # `kaggle competitions list` shows with no flags).
    body = {
        "sortBy": "COMPETITION_SORT_BY_RECENTLY_CREATED",
        "pageSize": page_size,
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, trust_env=False) as client:
            response = await client.post(
                LIST_COMPETITIONS_URL,
                json=body,
                auth=httpx.BasicAuth(username, key),
                headers={"User-Agent": DEFAULT_USER_AGENT, "Content-Type": "application/json"},
            )
    except httpx.TransportError as e:
        raise RuntimeError(f"Kaggle API request failed: {e}") from e

    if response.status_code == 401:
        raise RuntimeError(
            "Kaggle API rejected KAGGLE_USERNAME/KAGGLE_KEY (401 Unauthenticated). "
            "Regenerate a token at https://www.kaggle.com/settings/account and "
            "update your .env file."
        )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Kaggle API request failed: {e}") from e

    payload = response.json()
    competitions = payload.get("competitions") if isinstance(payload, dict) else None

    problems: list[dict] = []
    for item in competitions or []:
        if not isinstance(item, dict):
            continue
        mapped = _map_competition(item)
        if mapped:
            problems.append(mapped)
        if len(problems) >= max_items:
            break

    print(f"Kaggle Competitions: Extracted {len(problems)} problems (requested pageSize={page_size})")
    return problems
