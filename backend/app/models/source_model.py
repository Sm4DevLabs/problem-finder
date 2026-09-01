from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database_session import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    source_type: Mapped[str] = mapped_column(nullable=False)
    homepage_url: Mapped[str | None] = mapped_column(nullable=True)
    collection_method: Mapped[str | None] = mapped_column(
        SAEnum("API", "WEB_SCRAPING", "MANUAL", name="collection_method_enum"),
        nullable=True,
    )
    assessment_status: Mapped[str | None] = mapped_column(nullable=True, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
