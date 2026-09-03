from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database_session import Base


class SourceItem(Base):
    """
    Stores individual problems/items collected from sources.

    Each item represents one problem collected from a source
    (e.g., one ProblemHunt submission, one Razorpay issue).
    """

    __tablename__ = "source_items"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )

    # Original data from source
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Enriched fields (scraped when available, otherwise AI-generated)
    problem_frequency: Mapped[str | None] = mapped_column(Text, nullable=True)
    existing_solutions: Mapped[str | None] = mapped_column(Text, nullable=True)
    pricing_estimate: Mapped[str | None] = mapped_column(Text, nullable=True)
    problem_author: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Solution classification (AI-generated): which software mediums can solve this
    # problem (e.g. Web App, Mobile App, Browser Extension) or "Not Software-Solvable",
    # plus a short description of how it could be solved.
    solution_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    solution_approach: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Tech stack recommendations (AI-generated)
    tech_stack_options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommended_tech_stack: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tech_stack_justification: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
