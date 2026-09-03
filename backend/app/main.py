from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.ai_controller import router as ai_router
from app.api.source_controller import router as source_router
from app.api.source_item_controller import router as source_item_router

origins = [
    "http://localhost:5173",  # React development server
]
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, PUT, DELETE)
    allow_headers=["*"],  # Allows all headers
)


app.include_router(source_router)
app.include_router(ai_router)
app.include_router(source_item_router)


@app.get("/health")
async def read_db_health():
    from app.database.database_session import AsyncSessionLocal

    from app.services import llm_service

    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("SELECT 1"))
            return {
                "status": "OK",
                "service": "Problem Finder",
                "version": "1.0.0",
                "database": "Connected",
                "ai_provider": llm_service.active_provider(),
                "ai_model": llm_service.active_model(),
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "service": "Problem Finder",
                "version": "1.0.0",
                "database": str(e),
            }
