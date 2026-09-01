from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SourceCreate(BaseModel):
    name: str
    source_type: str
    homepage_url: Optional[str] = None
    collection_method: Optional[str] = None
    assessment_status: Optional[str] = None


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_type: str
    homepage_url: Optional[str] = None
    collection_method: Optional[str] = None
    assessment_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SourceAssessmentResponse(BaseModel):
    """Response after assessing a source with AI"""

    model_config = ConfigDict(from_attributes=True)

    # Updated source data
    id: UUID
    name: str
    source_type: str
    homepage_url: Optional[str] = None
    collection_method: Optional[str] = None
    assessment_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime
