from uuid import UUID

from app.database.database_session import DbSession
from app.repositories import source_repository
from app.schemas.source_schema import SourceCreate


async def get_all_sources(session: DbSession):
    return await source_repository.get_all_sources(session)


async def get_source_by_id(session: DbSession, source_id: UUID):
    return await source_repository.get_source_by_id(session, source_id)


async def create_source(session: DbSession, source_data: SourceCreate):
    return await source_repository.create_source(session, source_data.model_dump())


async def update_source(session: DbSession, source_id: UUID, source_data: SourceCreate):
    return await source_repository.update_source(session, source_id, source_data.model_dump())


async def delete_source(session: DbSession, source_id: UUID):
    return await source_repository.delete_source(session, source_id)
