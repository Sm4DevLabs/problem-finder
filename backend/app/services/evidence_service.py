import hashlib
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment_evidence_model import AssessmentEvidence
from app.schemas.evidence_schema import EvidenceSummary


# Known API documentation URLs for common sources
KNOWN_API_DOCS = {
    "Reddit": "https://www.reddit.com/dev/api",
    "GitHub Issues": "https://docs.github.com/en/rest/issues",
    "Kaggle Competitions": "https://www.kaggle.com/docs/api",
    "Kaggle Datasets": "https://www.kaggle.com/docs/api",
    "Data.gov": "https://www.data.gov/developers/apis",
    "Civic Tech Field Guide": "https://airtable.com/appRlfCvILXVf9GKX/api/docs",
}


async def collect_evidence_for_source(session: AsyncSession, source_id: UUID, source_name: str, homepage_url: str | None):
    """
    Collect evidence for a source by fetching key URLs.

    This is a SAFE, limited fetch - only predefined URLs, no crawling.

    Args:
        session: Database session
        source_id: Source UUID
        source_name: Source name (to lookup known API docs)
        homepage_url: Source homepage

    Returns:
        Number of evidence records created
    """
    evidence_count = 0

    # 1. Check for known API documentation
    if source_name in KNOWN_API_DOCS:
        api_doc_url = KNOWN_API_DOCS[source_name]
        evidence = await _fetch_and_store_evidence(
            session=session,
            source_id=source_id,
            evidence_type="API_DOCS",
            url=api_doc_url,
        )
        if evidence:
            evidence_count += 1

    # 2. Fetch robots.txt if homepage exists
    if homepage_url:
        # Store homepage as evidence
        homepage_evidence = await _store_evidence_without_fetch(
            session=session,
            source_id=source_id,
            evidence_type="HOMEPAGE",
            url=homepage_url,
            fetch_status="KNOWN",
        )
        if homepage_evidence:
            evidence_count += 1

        # Try to fetch robots.txt
        robots_url = _build_robots_url(homepage_url)
        robots_evidence = await _fetch_and_store_evidence(
            session=session,
            source_id=source_id,
            evidence_type="ROBOTS_TXT",
            url=robots_url,
        )
        if robots_evidence:
            evidence_count += 1

    return evidence_count


async def _fetch_and_store_evidence(
    session: AsyncSession,
    source_id: UUID,
    evidence_type: str,
    url: str,
    max_excerpt_length: int = 2000,
) -> AssessmentEvidence | None:
    """
    Fetch a URL and store it as evidence.

    Args:
        session: Database session
        source_id: Source UUID
        evidence_type: Type of evidence
        url: URL to fetch
        max_excerpt_length: Max characters to store

    Returns:
        Created evidence record or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)

            if response.status_code == 200:
                content = response.text[:max_excerpt_length]
                content_hash = hashlib.sha256(content.encode()).hexdigest()

                evidence = AssessmentEvidence(
                    source_id=source_id,
                    evidence_type=evidence_type,
                    url=url,
                    content_excerpt=content,
                    fetch_status="SUCCESS",
                    fetched_at=datetime.now(timezone.utc),
                    content_hash=content_hash,
                )
            elif response.status_code == 404:
                evidence = AssessmentEvidence(
                    source_id=source_id,
                    evidence_type=evidence_type,
                    url=url,
                    content_excerpt=None,
                    fetch_status="NOT_FOUND",
                    fetched_at=datetime.now(timezone.utc),
                )
            else:
                evidence = AssessmentEvidence(
                    source_id=source_id,
                    evidence_type=evidence_type,
                    url=url,
                    content_excerpt=f"HTTP {response.status_code}",
                    fetch_status="FAILED",
                    fetched_at=datetime.now(timezone.utc),
                )

            session.add(evidence)
            await session.commit()
            return evidence

    except Exception as e:
        # Store failure record
        evidence = AssessmentEvidence(
            source_id=source_id,
            evidence_type=evidence_type,
            url=url,
            content_excerpt=str(e)[:500],
            fetch_status="FAILED",
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(evidence)
        await session.commit()
        return evidence


async def _store_evidence_without_fetch(
    session: AsyncSession,
    source_id: UUID,
    evidence_type: str,
    url: str,
    fetch_status: str,
) -> AssessmentEvidence:
    """Store evidence record without fetching (e.g., homepage URL)."""
    evidence = AssessmentEvidence(
        source_id=source_id,
        evidence_type=evidence_type,
        url=url,
        content_excerpt=None,
        fetch_status=fetch_status,
        fetched_at=datetime.now(timezone.utc),
    )
    session.add(evidence)
    await session.commit()
    return evidence


def _build_robots_url(homepage_url: str) -> str:
    """Build robots.txt URL from homepage."""
    from urllib.parse import urlparse

    parsed = urlparse(homepage_url)
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


async def get_evidence_summary(session: AsyncSession, source_id: UUID) -> EvidenceSummary:
    """
    Get a summary of collected evidence for a source.

    This is what the AI will see when making assessment decisions.

    Args:
        session: Database session
        source_id: Source UUID

    Returns:
        Evidence summary for AI analysis
    """
    result = await session.execute(
        select(AssessmentEvidence).where(AssessmentEvidence.source_id == source_id)
    )
    evidence_list = result.scalars().all()

    summary = EvidenceSummary()

    for evidence in evidence_list:
        if evidence.evidence_type == "HOMEPAGE":
            summary.homepage = evidence.url

        elif evidence.evidence_type == "API_DOCS" and evidence.fetch_status == "SUCCESS":
            summary.api_docs_url = evidence.url
            summary.api_docs_excerpt = evidence.content_excerpt
            summary.has_documented_api = True

        elif evidence.evidence_type == "ROBOTS_TXT" and evidence.fetch_status == "SUCCESS":
            summary.robots_txt = evidence.content_excerpt

        elif evidence.evidence_type == "GITHUB_REPOSITORY":
            summary.github_repository = evidence.url

    # Determine evidence quality
    if summary.has_documented_api:
        summary.evidence_quality = "COMPLETE"
    elif summary.homepage:
        summary.evidence_quality = "PARTIAL"
    else:
        summary.evidence_quality = "NONE"

    return summary
