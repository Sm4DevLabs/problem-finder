from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database_session import Base


class Source(Base):
    __tablename__ = "sources"

    # Core fields
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    source_type: Mapped[str] = mapped_column(nullable=False)
    homepage_url: Mapped[str | None] = mapped_column(nullable=True)
    collection_method: Mapped[str | None] = mapped_column(
        SAEnum("API", "WEB_SCRAPING", "MANUAL", name="collection_method_enum"),
        nullable=True,
    )
    assessment_status: Mapped[str | None] = mapped_column(nullable=True, default="PENDING")

    # Assessment metadata fields
    assessment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    assessment_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assessed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Evidence fields
    api_documentation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    terms_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    robots_txt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    github_repository_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
