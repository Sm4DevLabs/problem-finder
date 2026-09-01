from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCreate(BaseModel):
    """Schema for creating evidence records."""

    source_id: UUID
    evidence_type: str = Field(..., description="API_DOCS, ROBOTS_TXT, TERMS, GITHUB_REPOSITORY, HOMEPAGE")
    url: str = Field(..., max_length=500)
    content_excerpt: str | None = Field(None, description="Key excerpt for AI analysis")
    fetch_status: str = Field(..., description="SUCCESS, NOT_FOUND, FAILED, BLOCKED")
    content_hash: str | None = Field(None, max_length=64)


class EvidenceRead(BaseModel):
    """Schema for reading evidence records."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    evidence_type: str
    url: str
    content_excerpt: str | None
    fetch_status: str
    fetched_at: datetime
    content_hash: str | None
    created_at: datetime


class EvidenceSummary(BaseModel):
    """Summary of evidence for a source - what the AI sees."""

    homepage: str | None = None
    api_docs_url: str | None = None
    api_docs_excerpt: str | None = None
    robots_txt: str | None = None
    terms_url: str | None = None
    github_repository: str | None = None
    has_documented_api: bool = False
    evidence_quality: str = "NONE"  # NONE, PARTIAL, COMPLETE
