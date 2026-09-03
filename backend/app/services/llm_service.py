"""
Provider-agnostic LLM helper for JSON responses.

Uses a hosted NVIDIA NIM model (OpenAI-compatible API) when ``NVIDIA_API_KEY`` is
configured — much more accurate and faster than the tiny local model, especially
for nuanced judgments like whether a problem is software-solvable. Falls back to
local Ollama when no key is present, so local development keeps working offline.
"""

import asyncio
import json

import httpx
import ollama

from app.database.database_session import settings


def active_provider() -> str:
    return "nim" if settings.NVIDIA_API_KEY else "ollama"


def active_model() -> str:
    return settings.NIM_MODEL if settings.NVIDIA_API_KEY else settings.OLLAMA_MODEL


def _extract_json(content: str) -> dict:
    """Parse a JSON object from a model response, tolerating markdown fences."""
    text = (content or "").strip()
    if text.startswith("```"):
        # strip ```json ... ``` fences
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


async def _nim_chat(prompt: str, *, temperature: float) -> str:
    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Accept": "application/json",
    }
    payload = {
        "model": settings.NIM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 1600,
        "response_format": {"type": "json_object"},
    }
    url = f"{settings.NIM_BASE_URL.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 400:
            # Some NIM models reject response_format; retry without it.
            payload.pop("response_format", None)
            resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


async def _ollama_chat(prompt: str) -> str:
    # ollama.chat is blocking; run it off the event loop.
    response = await asyncio.to_thread(
        ollama.chat,
        model=settings.OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        format="json",
    )
    return response["message"]["content"]


async def chat_json(prompt: str, *, temperature: float = 0.3) -> dict:
    """Send a prompt and parse a JSON object from the response.

    Raises on transport errors or unparseable output; callers decide how to
    handle failures (enrichment degrades gracefully per item).
    """
    if settings.NVIDIA_API_KEY:
        content = await _nim_chat(prompt, temperature=temperature)
    else:
        content = await _ollama_chat(prompt)
    return _extract_json(content)
