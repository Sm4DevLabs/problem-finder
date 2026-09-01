from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database_session import Base


class AssessmentEvidence(Base):
    """
    Stores evidence collected for source assessments.

    Each record represents one piece of evidence (API docs, robots.txt, etc.)
    fetched for a source to inform AI assessment decisions.

    Unique constraint: (source_id, evidence_type, url)
    This ensures idempotent evidence collection - one record per evidence item.
    """

    __tablename__ = "assessment_evidence"
    __table_args__ = (
        UniqueConstraint('source_id', 'evidence_type', 'url', name='uq_source_evidence_url'),
        Index('ix_assessment_evidence_source_id', 'source_id'),
        Index('ix_assessment_evidence_evidence_type', 'evidence_type'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)

    # Type of evidence: API_DOCS, ROBOTS_TXT, TERMS, GITHUB_REPOSITORY, HOMEPAGE
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # URL where evidence was fetched from
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Excerpt of content (not full content - just key parts for AI analysis)
    content_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Fetch status: SUCCESS, NOT_FOUND, FAILED, BLOCKED
    fetch_status: Mapped[str] = mapped_column(String(20), nullable=False)

    # When the evidence was fetched
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)

    # Hash of content to detect changes
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    # Relationship to source (optional - for easier querying)
    # source = relationship("Source", back_populates="evidence")
