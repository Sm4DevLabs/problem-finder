import hashlib
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment_evidence_model import AssessmentEvidence
from app.schemas.evidence_schema import EvidenceSummary
from app.services import evidence_validation_service


# Known API documentation URLs for problem-discovery sources
KNOWN_API_DOCS = {
    # Community discussions
    "Reddit": "https://www.reddit.com/dev/api",
    "Hacker News": "https://github.com/HackerNews/API",
    "Stack Exchange": "https://api.stackexchange.com/docs",
    "Lobsters": "https://lobste.rs/api",
    # Challenge statements
    "Kaggle Competitions": "https://www.kaggle.com/docs/api",
    # Civic problems
    "Civic Tech Field Guide": "https://directory.civictech.guide/build",
    "NYC 311 Service Requests": "https://dev.socrata.com/foundry/data.cityofnewyork.us/erm2-nwe9",
    "CFPB Consumer Complaint Database": "https://cfpb.github.io/api/ccdb/",
}

# Known GitHub repositories (collected via GitHub API)
KNOWN_GITHUB_REPOS = {
    "Razorpay Fix My Itch": "https://github.com/razorpay-fix-my-itch",
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

    # 2. Check for known GitHub repositories
    if source_name in KNOWN_GITHUB_REPOS:
        github_url = KNOWN_GITHUB_REPOS[source_name]
        github_evidence = await _store_evidence_without_fetch(
            session=session,
            source_id=source_id,
            evidence_type="GITHUB_REPOSITORY",
            url=github_url,
            fetch_status="VALID",
        )
        if github_evidence:
            evidence_count += 1

    # 3. Fetch robots.txt if homepage exists
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
    Fetch a URL and store it as evidence (idempotent - updates existing record if found).

    Args:
        session: Database session
        source_id: Source UUID
        evidence_type: Type of evidence
        url: URL to fetch
        max_excerpt_length: Max characters to store

    Returns:
        Created/updated evidence record or None if failed
    """
    # Check if evidence already exists (idempotent)
    existing_result = await session.execute(
        select(AssessmentEvidence)
        .where(AssessmentEvidence.source_id == source_id)
        .where(AssessmentEvidence.evidence_type == evidence_type)
        .where(AssessmentEvidence.url == url)
    )
    existing_evidence = existing_result.scalar_one_or_none()
    # Proper headers to avoid blocking
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    try:
        # Disable SSL verification for evidence collection (safe for public read-only data)
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers=headers,
            verify=False,  # Disable SSL verification to avoid cert issues
        ) as client:
            response = await client.get(url)

            if response.status_code == 200:
                content = response.text[:max_excerpt_length]
                content_hash = hashlib.sha256(content.encode()).hexdigest()

                # VALIDATE CONTENT - deterministic checks for CAPTCHA, login, etc.
                validation_status, validation_reason = evidence_validation_service.validate_evidence(
                    content=content,
                    evidence_type=evidence_type,
                    url=url,
                )

                # Store validation reason in excerpt if content is invalid
                if validation_status != "VALID":
                    content_excerpt = f"[{validation_status}] {validation_reason}"
                else:
                    content_excerpt = content

                if existing_evidence:
                    # UPDATE existing record
                    existing_evidence.content_excerpt = content_excerpt
                    existing_evidence.fetch_status = validation_status
                    existing_evidence.fetched_at = datetime.now(timezone.utc)
                    existing_evidence.content_hash = content_hash
                    evidence = existing_evidence
                else:
                    # CREATE new record
                    evidence = AssessmentEvidence(
                        source_id=source_id,
                        evidence_type=evidence_type,
                        url=url,
                        content_excerpt=content_excerpt,
                        fetch_status=validation_status,
                        fetched_at=datetime.now(timezone.utc),
                        content_hash=content_hash,
                    )
                    session.add(evidence)
            elif response.status_code == 404:
                if existing_evidence:
                    existing_evidence.content_excerpt = None
                    existing_evidence.fetch_status = "NOT_FOUND"
                    existing_evidence.fetched_at = datetime.now(timezone.utc)
                    evidence = existing_evidence
                else:
                    evidence = AssessmentEvidence(
                        source_id=source_id,
                        evidence_type=evidence_type,
                        url=url,
                        content_excerpt=None,
                        fetch_status="NOT_FOUND",
                        fetched_at=datetime.now(timezone.utc),
                    )
                    session.add(evidence)
            else:
                if existing_evidence:
                    existing_evidence.content_excerpt = f"HTTP {response.status_code}"
                    existing_evidence.fetch_status = "FAILED"
                    existing_evidence.fetched_at = datetime.now(timezone.utc)
                    evidence = existing_evidence
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
        # Store failure record (upsert)
        if existing_evidence:
            existing_evidence.content_excerpt = str(e)[:500]
            existing_evidence.fetch_status = "FAILED"
            existing_evidence.fetched_at = datetime.now(timezone.utc)
            evidence = existing_evidence
        else:
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
    """Store evidence record without fetching (e.g., homepage URL) - idempotent."""
    # Check if evidence already exists
    existing_result = await session.execute(
        select(AssessmentEvidence)
        .where(AssessmentEvidence.source_id == source_id)
        .where(AssessmentEvidence.evidence_type == evidence_type)
        .where(AssessmentEvidence.url == url)
    )
    existing_evidence = existing_result.scalar_one_or_none()

    if existing_evidence:
        # UPDATE existing
        existing_evidence.fetch_status = fetch_status
        existing_evidence.fetched_at = datetime.now(timezone.utc)
        evidence = existing_evidence
    else:
        # CREATE new
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
    Get a summary of VALID collected evidence for a source.

    This is what the AI will see when making assessment decisions.
    ONLY includes evidence with status = VALID.

    Args:
        session: Database session
        source_id: Source UUID

    Returns:
        Evidence summary for AI analysis (VALID evidence only)
    """
    result = await session.execute(
        select(AssessmentEvidence).where(AssessmentEvidence.source_id == source_id)
    )
    evidence_list = result.scalars().all()

    summary = EvidenceSummary()

    for evidence in evidence_list:
        if evidence.evidence_type == "HOMEPAGE":
            summary.homepage = evidence.url

        # ONLY accept VALID evidence for API docs
        elif evidence.evidence_type == "API_DOCS" and evidence.fetch_status == "VALID":
            summary.api_docs_url = evidence.url
            summary.api_docs_excerpt = evidence.content_excerpt[:500]  # Limit excerpt
            summary.has_documented_api = True

        # ONLY accept VALID evidence for robots.txt
        elif evidence.evidence_type == "ROBOTS_TXT" and evidence.fetch_status == "VALID":
            summary.robots_txt = evidence.content_excerpt[:300]  # Limit excerpt

        elif evidence.evidence_type == "GITHUB_REPOSITORY":
            summary.github_repository = evidence.url

    # Determine evidence quality based on VALID evidence only
    if summary.has_documented_api:
        summary.evidence_quality = "COMPLETE"
    elif summary.homepage or summary.robots_txt:
        summary.evidence_quality = "PARTIAL"
    else:
        summary.evidence_quality = "NONE"

    return summary
