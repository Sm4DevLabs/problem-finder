"""Adapter contract shared by every connector in app/connectors/adapters/.

Each adapter module exports a single coroutine:

    async def fetch(limit: int | None = None) -> list[dict]

Returned dicts must contain: external_id, title, description, url,
problem_frequency, existing_solutions, pricing_estimate, problem_author,
raw_data. See app/connectors/common.py for shared helpers building that
shape, and app/connectors/clients/ for the shared HTTP clients (api_client
for JSON REST APIs, crawlviel_client for JS-rendered / CMS-driven pages).
"""

from typing import Awaitable, Callable, Protocol


class Adapter(Protocol):
    async def __call__(self, limit: int | None = None) -> list[dict]: ...


FetchFn = Callable[..., Awaitable[list[dict]]]
