from uuid import UUID

from app.database.database_session import DbSession
from app.repositories import source_repository
from app.schemas.source_schema import SourceCreate
from app.services import ollama_service


async def get_all_sources(session: DbSession):
    return await source_repository.get_all_sources(session)


async def get_source_by_id(session: DbSession, source_id: UUID):
    return await source_repository.get_source_by_id(session, source_id)


async def create_source(session: DbSession, source_data: SourceCreate):
    return await source_repository.create_source(session, source_data.model_dump())


async def update_source(session: DbSession, source_id: UUID, source_data: SourceCreate):
    return await source_repository.update_source(session, source_id, source_data.model_dump())


async def delete_source(session: DbSession, source_id: UUID):
    return await source_repository.delete_source(session, source_id)


async def assess_source(session: DbSession, source):
    """
    Assess a source using Ollama AI to determine the best data collection method.

    Business Logic Flow:
    1. Extract source information (name, type, URL)
    2. Send to Ollama for AI analysis
    3. Receive structured assessment result
    4. Update source in database with findings
    5. Return updated source

    Args:
        session: Database session
        source: Source model instance to assess

    Returns:
        Updated source with assessment results

    Raises:
        Exception if Ollama fails or returns invalid data
    """
    # Step 1: Call Ollama AI to analyze this source
    assessment = await ollama_service.assess_source_with_ollama(
        source_name=source.name,
        source_type=source.source_type,
        homepage_url=source.homepage_url or "No URL provided",
    )

    # Step 2: Update the source with AI recommendations
    source.collection_method = assessment.recommended_method
    source.assessment_status = "ASSESSED"

    # Step 3: Commit changes to database
    await session.commit()
    await session.refresh(source)

    return source


async def assess_all_sources(session: DbSession):
    """
    Batch assess all sources that have status 'PENDING'.

    This skips already-assessed sources to avoid redundant AI calls.
    Use single assessment endpoint to re-assess a specific source.

    Returns:
        dict with assessment summary:
        - assessed_count: Number of sources assessed
        - skipped_count: Number already assessed (skipped)
        - failed_count: Number that failed
        - results: List of assessment results
    """
    all_sources = await get_all_sources(session)

    assessed_count = 0
    skipped_count = 0
    failed_count = 0
    results = []

    for source in all_sources:
        # Skip sources that are already assessed
        if source.assessment_status == "ASSESSED":
            skipped_count += 1
            results.append(
                {
                    "source_id": str(source.id),
                    "source_name": source.name,
                    "status": "skipped",
                    "reason": "Already assessed",
                }
            )
            continue

        # Assess pending sources
        try:
            updated_source = await assess_source(session, source)
            assessed_count += 1
            results.append(
                {
                    "source_id": str(updated_source.id),
                    "source_name": updated_source.name,
                    "status": "success",
                    "recommended_method": updated_source.collection_method,
                }
            )
        except Exception as e:
            failed_count += 1
            results.append(
                {
                    "source_id": str(source.id),
                    "source_name": source.name,
                    "status": "failed",
                    "error": str(e),
                }
            )

    return {
        "total_sources": len(all_sources),
        "assessed_count": assessed_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "results": results,
    }
