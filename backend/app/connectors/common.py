"""Shared helpers for connector adapters mapping raw items into the SourceItem shape.

Every adapter's ``fetch(limit)`` returns a list of dicts with this shape:

    external_id, title, description, url, problem_frequency,
    existing_solutions, pricing_estimate, problem_author, raw_data

``problem_frequency`` / ``existing_solutions`` / ``pricing_estimate`` /
``problem_author`` may be None when the source doesn't provide them; the
enrichment service (app/services/problem_enrichment_service.py) fills gaps
and always brainstorms tech stacks downstream. Adapters never set
solution_tags, solution_approach, or tech_stack_* directly.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


def stable_id(source_key: str, natural_key: str) -> str:
    """Deterministic external_id so re-fetching the same item updates, not duplicates."""
    digest = hashlib.sha256(natural_key.strip().encode("utf-8")).hexdigest()[:20]
    return f"{source_key}-{digest}"


def build_raw_data(
    source_key: str,
    url: str,
    *,
    strategy: str,
    category: str | None = None,
    industry: str | None = None,
    score: float | int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the standard raw_data envelope stored alongside every item."""
    data: dict[str, Any] = {
        "source": source_key,
        "strategy": strategy,
        "category": category,
        "industry": industry,
        "score": score,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "host": urlparse(url).netloc,
    }
    if extra:
        data.update(extra)
    return data


def truncate_title(title: str, max_len: int = 500) -> str:
    return title.strip()[:max_len]
