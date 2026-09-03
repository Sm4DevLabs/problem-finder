from typing import Annotated, AsyncGenerator

from fastapi import Depends
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Settings(BaseSettings):
    DATABASE_URL: str
    OLLAMA_BASE_URL: str
    OLLAMA_MODEL: str
    CRAWLVIEL_API_URL: str = "https://crawlviel-api.sm4devlabs.dpdns.org"
    # Max problems AI-enriched per fetch (keeps the synchronous fetch responsive;
    # each enrichment is one Ollama call).
    FETCH_ENRICH_LIMIT: int = 8

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

engine = create_async_engine(settings.DATABASE_URL, echo=True)
# Create a session factory for generating database workers
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# Modern SQLAlchemy 2.0 Base model inheritance class
class Base(DeclarativeBase):
    pass


# FastAPI Dependency injection to provide an async session per web request
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


DbSession = Annotated[AsyncSession, Depends(get_db)]
