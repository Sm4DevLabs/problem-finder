from pydantic import BaseModel, Field


class AssessmentResult(BaseModel):
    """
    Structured output from Ollama for source assessment.
    This schema enforces the JSON structure we expect from the AI.
    """

    recommended_method: str = Field(
        ...,
        description="Must be one of: API, WEB_SCRAPING, or MANUAL",
    )
    reason: str = Field(
        ...,
        description="Evidence-based explanation for the recommendation",
        min_length=10,
    )
    confidence: float = Field(
        ...,
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0,
    )
    evidence_needed: list[str] = Field(
        default_factory=list,
        description="List of things that still need verification",
    )
