from uuid import UUID

from app.database.database_session import DbSession
from app.repositories import source_repository
from app.schemas.source_schema import SourceCreate
from app.services import evidence_service, ollama_service


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
    Assess a source using Ollama AI with collected evidence.

    NEW Flow with Evidence:
    1. Collect evidence (API docs, robots.txt, etc.)
    2. Build evidence summary for AI
    3. Send evidence + source info to Ollama
    4. Receive structured assessment result
    5. Update source in database with findings
    6. Return updated source

    Args:
        session: Database session
        source: Source model instance to assess

    Returns:
        Updated source with assessment results

    Raises:
        Exception if Ollama fails or returns invalid data
    """
    from datetime import datetime, timezone
    from app.database.database_session import settings

    # Step 1: Collect evidence for this source
    evidence_count = await evidence_service.collect_evidence_for_source(
        session=session,
        source_id=source.id,
        source_name=source.name,
        homepage_url=source.homepage_url,
    )

    # Step 2: Get evidence summary for AI
    evidence_summary = await evidence_service.get_evidence_summary(
        session=session,
        source_id=source.id,
    )

    # Step 3: Call Ollama AI with evidence
    assessment = await ollama_service.assess_source_with_evidence(
        source_name=source.name,
        source_type=source.source_type,
        homepage_url=source.homepage_url or "No URL provided",
        evidence_summary=evidence_summary,
    )

    # Step 4: Update the source with AI recommendations AND metadata
    source.collection_method = assessment.recommended_method
    source.assessment_status = "ASSESSED"

    # Save assessment metadata
    source.assessment_reason = assessment.reason
    source.assessment_confidence = assessment.confidence
    source.assessment_model = settings.OLLAMA_MODEL
    source.assessed_at = datetime.now(timezone.utc)

    # Save evidence summary in source for quick reference
    if evidence_summary.has_documented_api:
        source.evidence_summary = f"API documentation found at {evidence_summary.api_docs_url}"
    elif evidence_summary.evidence_quality == "PARTIAL":
        source.evidence_summary = f"Evidence collected: {evidence_count} records"
    else:
        source.evidence_summary = "No evidence collected"

    # Step 5: Commit changes to database
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
