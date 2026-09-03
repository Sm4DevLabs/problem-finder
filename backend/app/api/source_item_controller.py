"""API endpoints for source items (collected problems)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.database.database_session import DbSession
from app.schemas.source_item_schema import FetchResult, SourceItemResponse
from app.services import source_item_service

router = APIRouter(prefix="/api/source-items", tags=["source-items"])


@router.post("/{source_id}/fetch", response_model=FetchResult)
async def fetch_items(source_id: UUID, session: DbSession, limit: int | None = None):
    """
    Fetch items from a source using its connector.

    This triggers the connector to fetch new problems from the source, AI-enriches
    each one (missing fields + solution tags + tech stacks), and stores them.

    Args:
        limit: Max problems to fetch + enrich this run. Each enrichment is one
            Ollama call; defaults to settings.FETCH_ENRICH_LIMIT to keep the
            synchronous request responsive.
    """
    try:
        result = await source_item_service.fetch_items_for_source(session, source_id, limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{source_id}", response_model=list[SourceItemResponse])
async def get_items_by_source(source_id: UUID, limit: int = 50, session: DbSession = None):
    """Get all items for a specific source."""
    items = await source_item_service.get_items_for_source(session, source_id, limit)
    return items


@router.get("/", response_model=list[SourceItemResponse])
async def get_all_items(limit: int = 100, offset: int = 0, session: DbSession = None):
    """Get a page of items across all sources (supports limit/offset paging)."""
    items = await source_item_service.get_all_items(session, limit, offset)
    return items


@router.get("/item/{item_id}", response_model=SourceItemResponse)
async def get_item(item_id: UUID, session: DbSession):
    """Get a specific item by ID."""
    item = await source_item_service.get_item_by_id(session, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
