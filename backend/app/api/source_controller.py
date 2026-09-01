from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.database.database_session import DbSession
from app.schemas.source_schema import SourceCreate, SourceRead
from app.services import source_assessment_service


router = APIRouter(
    prefix="/sources",
    tags=["sources"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=list[SourceRead])
async def read_sources(session: DbSession):
    return await source_assessment_service.get_all_sources(session)


@router.get("/{source_id}", response_model=SourceRead)
async def read_source(source_id: UUID, session: DbSession):
    source = await source_assessment_service.get_source_by_id(session, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("/", response_model=SourceRead, status_code=201)
async def create_source(source_data: SourceCreate, session: DbSession):
    return await source_assessment_service.create_source(session, source_data)


@router.put("/{source_id}", response_model=SourceRead)
async def update_source(source_id: UUID, source_data: SourceCreate, session: DbSession):
    updated_source = await source_assessment_service.update_source(session, source_id, source_data)
    if not updated_source:
        raise HTTPException(status_code=404, detail="Source not found")
    return updated_source


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: UUID, session: DbSession):
    deleted_source = await source_assessment_service.delete_source(session, source_id)
    if not deleted_source:
        raise HTTPException(status_code=404, detail="Source not found")
