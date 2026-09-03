from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SourceItemBase(BaseModel):
    """Base schema for source items."""

    title: str
    description: str | None = None
    url: str | None = None
    problem_frequency: str | None = None
    existing_solutions: str | None = None
    pricing_estimate: str | None = None
    tech_stack_options: list | None = None  # List of TechStackOption dicts
    recommended_tech_stack: dict | None = None
    tech_stack_justification: str | None = None


class SourceItemCreate(SourceItemBase):
    """Schema for creating a source item."""

    source_id: UUID
    external_id: str
    raw_data: dict | None = None


class SourceItemResponse(SourceItemBase):
    """Schema for source item responses."""

    id: UUID
    source_id: UUID
    external_id: str
    raw_data: dict | None = None
    fetched_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class FetchResult(BaseModel):
    """Result of a fetch operation."""

    source_id: UUID
    source_name: str
    items_fetched: int
    items_new: int
    items_updated: int
    duration_seconds: float
