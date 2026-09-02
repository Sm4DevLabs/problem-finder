"""Service for managing source items (collected problems)."""

import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import problemhunt_connector, razorpay_connector
from app.models.source_item_model import SourceItem
from app.models.source_model import Source
from app.schemas.source_item_schema import FetchResult


async def fetch_items_for_source(session: AsyncSession, source_id: UUID) -> FetchResult:
    """
    Fetch items for a specific source using its connector.

    Args:
        session: Database session
        source_id: Source UUID

    Returns:
        FetchResult with statistics

    Raises:
        Exception if source not found or fetch fails
    """
    start_time = time.time()

    # Get source
    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()

    if not source:
        raise Exception(f"Source {source_id} not found")

    if not source.is_active:
        raise Exception(f"Source '{source.name}' is inactive")

    # Route to appropriate connector
    problems = await _fetch_from_connector(source.name)

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


async def _fetch_from_connector(source_name: str) -> list[dict]:
    """Route to appropriate connector based on source name."""
    if source_name == "ProblemHunt":
        return await problemhunt_connector.fetch_problems(limit=50)
    elif source_name == "Razorpay Fix My Itch":
        # Try website scraper first (gets 10,000+ problems)
        try:
            from app.connectors import razorpay_website_connector
            print("Using Razorpay website connector for 10,000+ problems...")
            problems = await razorpay_website_connector.fetch_problems(limit=200)
            if problems:
                return problems
        except Exception as e:
            print(f"Website connector failed: {e}, falling back to GitHub connector")

        # Fallback to GitHub connector
        return await razorpay_connector.fetch_problems(limit=20)
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


async def get_all_items(session: AsyncSession, limit: int = 100) -> list[SourceItem]:
    """Get all items across all sources."""
    result = await session.execute(
        select(SourceItem).order_by(SourceItem.fetched_at.desc()).limit(limit)
    )
    return result.scalars().all()


async def get_item_by_id(session: AsyncSession, item_id: UUID) -> SourceItem | None:
    """Get a specific item by ID."""
    result = await session.execute(select(SourceItem).where(SourceItem.id == item_id))
    return result.scalar_one_or_none()
