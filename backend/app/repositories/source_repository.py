from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_model import Source


async def get_all_sources(session: AsyncSession):
    result = await session.execute(select(Source))
    return result.scalars().all()


async def get_source_by_id(session: AsyncSession, source_id: UUID):
    result = await session.execute(select(Source).where(Source.id == source_id))
    return result.scalar_one_or_none()


async def create_source(session: AsyncSession, source_data: dict):
    new_source = Source(**source_data)
    session.add(new_source)
    await session.commit()
    await session.refresh(new_source)
    return new_source


async def update_source(session: AsyncSession, source_id: UUID, source_data: dict):
    source = await get_source_by_id(session, source_id)
    if source:
        for key, value in source_data.items():
            setattr(source, key, value)
        await session.commit()
        await session.refresh(source)
    return source


async def delete_source(session: AsyncSession, source_id: UUID):
    source = await get_source_by_id(session, source_id)
    if source:
        session.delete(source)  # No await - delete() is synchronous
        await session.commit()
    return source
