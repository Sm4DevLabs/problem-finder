"""Service for managing source items (collected problems)."""

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
        limit: Max problems to fetch + enrich this run (defaults to
            settings.FETCH_ENRICH_LIMIT). Each enrichment is one Ollama call, so
            this bounds the synchronous request time.

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

    # Route to appropriate connector (capped to the enrichment budget)
    problems = await _fetch_from_connector(source.name, effective_limit)

    # AI-enrich each problem: fill any missing analytical fields and always
    # brainstorm tech-stack options + recommendation.
    for problem in problems:
        await problem_enrichment_service.enrich_problem(problem)

    # Store items (upsert)
    items_new = 0
    items_updated = 0

    for problem in problems:
        existing_result = await session.execute(
            select(SourceItem)
            .where(SourceItem.source_id == source_id)
            .where(SourceItem.external_id == problem["external_id"])
        )
        existing_item = existing_result.scalar_one_or_none()

        if existing_item:
            # Update existing
            existing_item.title = problem["title"]
            existing_item.description = problem.get("description")
            existing_item.url = problem.get("url")
            existing_item.problem_frequency = problem.get("problem_frequency")
            existing_item.existing_solutions = problem.get("existing_solutions")
            existing_item.pricing_estimate = problem.get("pricing_estimate")
            existing_item.problem_author = problem.get("problem_author")
            existing_item.solution_tags = problem.get("solution_tags")
            existing_item.solution_approach = problem.get("solution_approach")
            existing_item.tech_stack_options = problem.get("tech_stack_options")
            existing_item.recommended_tech_stack = problem.get("recommended_tech_stack")
            existing_item.tech_stack_justification = problem.get("tech_stack_justification")
            existing_item.raw_data = problem.get("raw_data")
            existing_item.fetched_at = datetime.now(timezone.utc)
            items_updated += 1
        else:
            # Create new
            new_item = SourceItem(
                source_id=source_id,
                external_id=problem["external_id"],
                title=problem["title"],
                description=problem.get("description"),
                url=problem.get("url"),
                problem_frequency=problem.get("problem_frequency"),
                existing_solutions=problem.get("existing_solutions"),
                pricing_estimate=problem.get("pricing_estimate"),
                problem_author=problem.get("problem_author"),
                solution_tags=problem.get("solution_tags"),
                solution_approach=problem.get("solution_approach"),
                tech_stack_options=problem.get("tech_stack_options"),
                recommended_tech_stack=problem.get("recommended_tech_stack"),
                tech_stack_justification=problem.get("tech_stack_justification"),
                raw_data=problem.get("raw_data"),
                fetched_at=datetime.now(timezone.utc),
            )
            session.add(new_item)
            items_new += 1

    await session.commit()

    duration = time.time() - start_time

    return FetchResult(
        source_id=source_id,
        source_name=source.name,
        items_fetched=len(problems),
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
