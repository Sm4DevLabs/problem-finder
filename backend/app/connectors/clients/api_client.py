"""Generic JSON REST client shared by all API-type adapters.

Handles the boilerplate every adapter would otherwise duplicate: a shared
User-Agent, timeout, and retry-with-backoff on 429/5xx. Adapters own their
own pagination and query params since those differ per API.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = "ProblemFinder/1.0 (+https://github.com/subh2312/problem-finder)"
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


async def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = 3,
) -> Any:
    """GET a URL and return parsed JSON, retrying on rate-limit/server errors."""
    req_headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        for attempt in range(max_retries):
            try:
                response = await client.get(url, params=params, headers=req_headers)
                if response.status_code in _RETRYABLE_STATUS and attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

    raise RuntimeError(f"GET {url} failed after {max_retries} attempts: {last_error}")
