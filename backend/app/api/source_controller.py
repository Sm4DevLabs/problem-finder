from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.database.database_session import DbSession
from app.schemas.source_schema import SourceAssessmentResponse, SourceCreate, SourceRead
from app.services import source_assessment_service


router = APIRouter(
    prefix="/api/sources",
    tags=["sources"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=list[SourceRead])
async def read_sources(session: DbSession):
    return await source_assessment_service.get_all_sources(session)


@router.get("/{source_id}", response_model=SourceRead)
async def read_source(source_id: UUID, session: DbSession):
    source = await source_assessment_service.get_source_by_id(session, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("/", response_model=SourceRead, status_code=201)
async def create_source(source_data: SourceCreate, session: DbSession):
    return await source_assessment_service.create_source(session, source_data)


@router.put("/{source_id}", response_model=SourceRead)
async def update_source(source_id: UUID, source_data: SourceCreate, session: DbSession):
    updated_source = await source_assessment_service.update_source(session, source_id, source_data)
    if not updated_source:
        raise HTTPException(status_code=404, detail="Source not found")
    return updated_source


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: UUID, session: DbSession):
    deleted_source = await source_assessment_service.delete_source(session, source_id)
    if not deleted_source:
        raise HTTPException(status_code=404, detail="Source not found")

@router.post("/{source_id}/assess", response_model=SourceAssessmentResponse)
async def assess_source(source_id: UUID, session: DbSession):
    """
    Assess a single source using AI to determine the best data collection method.

    This endpoint allows re-assessment of already-assessed sources.
    Use this when you want to explicitly update a specific source.

    Flow:
    1. Fetches the source from the database
    2. Sends source info to Ollama AI for analysis
    3. Updates the source with AI recommendations
    4. Returns the updated source

    Returns:
        SourceAssessmentResponse with updated collection_method and assessment_status
    """
    source = await source_assessment_service.get_source_by_id(session, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    try:
        # Call AI assessment business logic (allows re-assessment)
        updated_source = await source_assessment_service.assess_source(session, source)
        return updated_source
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Assessment failed: {str(e)}",
        )


@router.post("/assess-all")
async def assess_all_sources(session: DbSession):
    """
    Batch assess all sources with status 'PENDING'.

    This skips sources that are already assessed to avoid redundant AI calls.
    Use the single assessment endpoint (/{source_id}/assess) to re-assess a specific source.

    Returns:
        dict with:
        - total_sources: Total number of sources
        - assessed_count: Sources successfully assessed
        - skipped_count: Already-assessed sources (skipped)
        - failed_count: Assessments that failed
        - results: List of per-source results
    """
    try:
        result = await source_assessment_service.assess_all_sources(session)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch assessment failed: {str(e)}",
        )