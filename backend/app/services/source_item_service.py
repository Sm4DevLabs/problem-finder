"""Service for managing source items (collected problems)."""

import asyncio
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import problemhunt_connector, razorpay_connector
from app.database.database_session import settings
from app.models.source_item_model import SourceItem
from app.models.source_model import Source
from app.schemas.source_item_schema import FetchResult
from app.services import problem_enrichment_service

# How many problems to enrich in parallel (bounded so we respect hosted-tier
# rate limits; llm_service retries on 429).
_ENRICH_CONCURRENCY = 3
# Persist progress after each chunk so a long run is resumable and never
# all-or-nothing.
_COMMIT_CHUNK = 6

_ITEM_FIELDS = (
    "title",
    "description",
    "url",
    "problem_frequency",
    "existing_solutions",
    "pricing_estimate",
    "problem_author",
    "solution_tags",
    "solution_approach",
    "tech_stack_options",
    "recommended_tech_stack",
    "tech_stack_justification",
    "raw_data",
)


def _is_enrichment_complete(item: SourceItem | None) -> bool:
    if item is None:
        return False
    tags = item.solution_tags
    if not tags:
        return False
    if tags == ["Not Software-Solvable"]:
        return True
    return bool(
        item.tech_stack_options
        and item.recommended_tech_stack
        and item.tech_stack_justification
    )


def _apply_fields(item: SourceItem, problem: dict) -> None:
    for field in _ITEM_FIELDS:
        if field in problem:
            setattr(item, field, problem[field])
    item.fetched_at = datetime.now(timezone.utc)


async def fetch_items_for_source(
    session: AsyncSession, source_id: UUID, limit: int | None = None
) -> FetchResult:
    """
    Fetch items for a specific source using its connector, then AI-enrich each
    problem (fill missing frequency/solutions/pricing and always brainstorm tech
    stacks) before storing.

    Args:
        session: Database session
        source_id: Source UUID
        limit: Max problems to pull from the connector this run (defaults to
            settings.FETCH_ENRICH_LIMIT). Already-enriched items are skipped, so
            repeated calls with a large limit resume until the catalog is covered.

    Returns:
        FetchResult with statistics

    Raises:
        Exception if source not found or fetch fails
    """
    start_time = time.time()
    effective_limit = limit if limit and limit > 0 else settings.FETCH_ENRICH_LIMIT

    # Get source
    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()

    if not source:
        raise Exception(f"Source {source_id} not found")

    if not source.is_active:
        raise Exception(f"Source '{source.name}' is inactive")

    # Route to appropriate connector
    problems = await _fetch_from_connector(source.name, effective_limit)

    # Map existing rows so we can skip already-enriched items (resumable).
    existing_rows = (
        await session.execute(select(SourceItem).where(SourceItem.source_id == source_id))
    ).scalars().all()
    existing_by_ext = {row.external_id: row for row in existing_rows}

    pending = [
        p
        for p in problems
        if not _is_enrichment_complete(existing_by_ext.get(p["external_id"]))
    ]

    semaphore = asyncio.Semaphore(_ENRICH_CONCURRENCY)

    async def _enrich(problem: dict) -> None:
        async with semaphore:
            await problem_enrichment_service.enrich_problem(problem)

    items_new = 0
    items_updated = 0

    # Enrich + persist in chunks so progress survives interruptions.
    for start in range(0, len(pending), _COMMIT_CHUNK):
        chunk = pending[start : start + _COMMIT_CHUNK]
        await asyncio.gather(*(_enrich(p) for p in chunk))

        for problem in chunk:
            existing_item = existing_by_ext.get(problem["external_id"])
            if existing_item:
                _apply_fields(existing_item, problem)
                items_updated += 1
            else:
                new_item = SourceItem(source_id=source_id, external_id=problem["external_id"])
                _apply_fields(new_item, problem)
                session.add(new_item)
                existing_by_ext[problem["external_id"]] = new_item
                items_new += 1

        await session.commit()

    duration = time.time() - start_time

    return FetchResult(
        source_id=source_id,
        source_name=source.name,
        items_fetched=len(pending),
        items_new=items_new,
        items_updated=items_updated,
        duration_seconds=round(duration, 2),
    )


async def _fetch_from_connector(source_name: str, limit: int) -> list[dict]:
    """Route to appropriate connector based on source name."""
    if source_name == "ProblemHunt":
        # Crawlviel Tilda Feed API — all published CMS records
        return await problemhunt_connector.fetch_problems(limit=limit)
    elif source_name == "Razorpay Fix My Itch":
        # Crawlviel Framer CMS — published curated set (not marketing 10k+)
        try:
            from app.connectors import razorpay_website_connector

            print("Using Crawlviel Framer connector for Fix My Itch...")
            problems = await razorpay_website_connector.fetch_problems(limit=limit)
            if problems:
                return problems
        except Exception as e:
            print(f"Crawlviel Razorpay connector failed: {e}, falling back to GitHub connector")

        return await razorpay_connector.fetch_problems(limit=limit)
    else:
        raise Exception(f"No connector implemented for source: {source_name}")


async def get_items_for_source(session: AsyncSession, source_id: UUID, limit: int = 50) -> list[SourceItem]:
    """Get all items for a source."""
    result = await session.execute(
        select(SourceItem)
        .where(SourceItem.source_id == source_id)
        .order_by(SourceItem.fetched_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def get_all_items(
    session: AsyncSession, limit: int = 100, offset: int = 0
) -> list[SourceItem]:
    """Get a page of items across all sources (newest first, stable ordering)."""
    result = await session.execute(
        select(SourceItem)
        .order_by(SourceItem.fetched_at.desc(), SourceItem.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def get_item_by_id(session: AsyncSession, item_id: UUID) -> SourceItem | None:
    """Get a specific item by ID."""
    result = await session.execute(select(SourceItem).where(SourceItem.id == item_id))
    return result.scalar_one_or_none()
