from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import ollama_service

router = APIRouter(
    prefix="/ai",
    tags=["ai"],
)


class TestPromptRequest(BaseModel):
    prompt: str


class TestPromptResponse(BaseModel):
    success: bool
    model: str
    response: str


@router.post("/test", response_model=TestPromptResponse)
async def test_ollama(request: TestPromptRequest):
    """
    Development endpoint to test Ollama integration.
    Sends a prompt to the local Ollama model and returns the response.
    """
    try:
        result = await ollama_service.chat_with_ollama(request.prompt)
        return TestPromptResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama is unavailable: {str(e)}",
        )

