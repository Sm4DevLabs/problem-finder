"""Service for managing source items (collected problems)."""

import asyncio
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.registry import ADAPTERS
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


def _apply_fields(item: SourceItem, problem: dict) -> None:
    for field in _ITEM_FIELDS:
        setattr(item, field, problem.get(field))
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
        if (existing_by_ext.get(p["external_id"]) is None)
        or (not existing_by_ext[p["external_id"]].solution_tags)
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
    """Route to the adapter registered for this source (app/connectors/registry.py)."""
    adapter = ADAPTERS.get(source_name)
    if not adapter:
        raise Exception(f"No connector implemented for source: {source_name}")
    return await adapter(limit)


async def get_items_for_source(session: AsyncSession, source_id: UUID, limit: int = 50) -> list[SourceItem]:
    """Get all items for a source."""
    result = await session.execute(
        select(SourceItem)
        .where(SourceItem.source_id == source_id)
        .order_by(SourceItem.fetched_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


def _apply_item_filters(stmt, source_id: UUID | None, tag: str | None, search: str | None):
    """Apply optional source / solution-tag / text-search filters to a query."""
    if source_id is not None:
        stmt = stmt.where(SourceItem.source_id == source_id)
    if tag:
        # jsonb_exists avoids the `?` operator (which clashes with param styles).
        stmt = stmt.where(
            text("jsonb_exists(source_items.solution_tags::jsonb, :tag)").bindparams(tag=tag)
        )
    if search and search.strip():
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(SourceItem.title.ilike(like), SourceItem.description.ilike(like))
        )
    return stmt


async def get_all_items(
    session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    source_id: UUID | None = None,
    tag: str | None = None,
    search: str | None = None,
) -> list[SourceItem]:
    """Get a page of items across all sources (newest first, stable ordering),
    optionally filtered by source, solution tag, and/or text search."""
    stmt = _apply_item_filters(select(SourceItem), source_id, tag, search)
    stmt = stmt.order_by(SourceItem.fetched_at.desc(), SourceItem.id.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_facets(
    session: AsyncSession,
    source_id: UUID | None = None,
    tag: str | None = None,
    search: str | None = None,
) -> dict:
    """Faceted counts for the filter UI.

    - ``total``   : problems matching ALL active filters (for the results header).
    - ``tags``    : per-tag counts, respecting source + search (not the tag itself),
                    so tag options always show reachable totals.
    - ``sources`` : per-source counts, respecting tag + search (not the source),
                    so only sources with matching items appear.
    """
    # total (all active filters)
    total_stmt = _apply_item_filters(
        select(func.count()).select_from(SourceItem), source_id, tag, search
    )
    total = (await session.execute(total_stmt)).scalar_one()

    # tag facet: respect source + search, ignore the active tag
    tag_where, tag_params = _sql_filters(source_id=source_id, search=search)
    tag_rows = (
        await session.execute(
            text(
                f"""
                SELECT t.tag AS tag, count(*) AS count
                FROM source_items si,
                     LATERAL jsonb_array_elements_text(si.solution_tags::jsonb) AS t(tag)
                WHERE si.solution_tags IS NOT NULL AND si.solution_tags::text <> 'null'
                {tag_where}
                GROUP BY t.tag
                ORDER BY count DESC, t.tag ASC
                """
            ).bindparams(**tag_params)
        )
    ).all()

    # source facet: respect tag + search, ignore the active source
    src_where, src_params = _sql_filters(tag=tag, search=search)
    src_rows = (
        await session.execute(
            text(
                f"""
                SELECT s.id AS source_id, s.name AS name, count(*) AS count
                FROM source_items si
                JOIN sources s ON s.id = si.source_id
                WHERE 1=1
                {src_where}
                GROUP BY s.id, s.name
                ORDER BY count DESC, s.name ASC
                """
            ).bindparams(**src_params)
        )
    ).all()

    return {
        "total": total,
        "tags": [{"tag": r.tag, "count": r.count} for r in tag_rows],
        "sources": [{"source_id": str(r.source_id), "name": r.name, "count": r.count} for r in src_rows],
    }


def _sql_filters(
    source_id: UUID | None = None, tag: str | None = None, search: str | None = None
) -> tuple[str, dict]:
    """Build a WHERE fragment (prefixed with AND) + bind params for raw facet SQL."""
    clauses: list[str] = []
    params: dict = {}
    if source_id is not None:
        # psycopg3 adapts a uuid.UUID to a Postgres uuid; avoid uuid = text errors.
        clauses.append("AND si.source_id = :source_id")
        params["source_id"] = source_id
    if tag:
        clauses.append("AND jsonb_exists(si.solution_tags::jsonb, :tag)")
        params["tag"] = tag
    if search and search.strip():
        clauses.append("AND (si.title ILIKE :search OR si.description ILIKE :search)")
        params["search"] = f"%{search.strip()}%"
    return "\n".join(clauses), params


async def get_item_by_id(session: AsyncSession, item_id: UUID) -> SourceItem | None:
    """Get a specific item by ID."""
    result = await session.execute(select(SourceItem).where(SourceItem.id == item_id))
    return result.scalar_one_or_none()
