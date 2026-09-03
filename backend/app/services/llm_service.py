"""
Provider-agnostic LLM helper for JSON responses.

Supports three providers, selected by ``settings.LLM_PROVIDER`` (default "auto"):

- "ollama_cloud" — Ollama Cloud (hosted, strong open models e.g. gpt-oss:120b).
- "nim"          — NVIDIA NIM (hosted, OpenAI-compatible).
- "ollama_local" — a local Ollama server (offline dev fallback).

"auto" picks the first hosted provider that has an API key, else local Ollama.
Hosted calls retry with exponential backoff on rate limits / transient errors,
because free tiers commonly return 429 and have variable latency.
"""

import asyncio
import json
import os

import httpx
import ollama

from app.database.database_session import settings

_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 4


def _ollama_cloud_key() -> str:
    # Accept several common secret names for convenience.
    return (
        settings.OLLAMA_CLOUD_API_KEY
        or os.getenv("OLLAMA_API_KEY", "")
        or os.getenv("OLLAMA_CLOUD_KEY", "")
    )


def resolve_provider() -> str:
    forced = (settings.LLM_PROVIDER or "auto").strip().lower()
    if forced in {"ollama_cloud", "nim", "ollama_local"}:
        return forced
    if _ollama_cloud_key():
        return "ollama_cloud"
    if settings.NVIDIA_API_KEY:
        return "nim"
    return "ollama_local"


def active_provider() -> str:
    return resolve_provider()


def active_model() -> str:
    provider = resolve_provider()
    if provider == "ollama_cloud":
        return settings.OLLAMA_CLOUD_MODEL
    if provider == "nim":
        return settings.NIM_MODEL
    return settings.OLLAMA_MODEL


def _extract_json(content: str) -> dict:
    """Parse a JSON object from a model response, tolerating markdown fences and
    surrounding prose/reasoning text."""
    text = (content or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


async def _post_with_retry(url: str, headers: dict, payload: dict) -> httpx.Response:
    delay = 2.0
    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=180.0, trust_env=False) as client:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in _RETRY_STATUS and attempt < _MAX_RETRIES:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                resp.raise_for_status()
                return resp
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_exc = e
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise
    if last_exc:
        raise last_exc
    raise RuntimeError("request failed without response")


async def _ollama_cloud_chat(prompt: str, temperature: float) -> str:
    url = f"{settings.OLLAMA_CLOUD_BASE_URL.rstrip('/')}/api/chat"
    headers = {"Authorization": f"Bearer {_ollama_cloud_key()}"}
    payload = {
        "model": settings.OLLAMA_CLOUD_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {"temperature": temperature},
    }
    resp = await _post_with_retry(url, headers, payload)
    return resp.json()["message"]["content"]


async def _nim_chat(prompt: str, temperature: float) -> str:
    url = f"{settings.NIM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Accept": "application/json",
    }
    payload = {
        "model": settings.NIM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 1600,
    }
    resp = await _post_with_retry(url, headers, payload)
    return resp.json()["choices"][0]["message"]["content"]


async def _ollama_local_chat(prompt: str) -> str:
    response = await asyncio.to_thread(
        ollama.chat,
        model=settings.OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        format="json",
    )
    return response["message"]["content"]


async def chat_json(prompt: str, *, temperature: float = 0.2) -> dict:
    """Send a prompt and parse a JSON object from the response.

    Raises on transport errors or unparseable output; callers decide how to
    handle failures (enrichment degrades gracefully per item).
    """
    provider = resolve_provider()
    if provider == "ollama_cloud":
        content = await _ollama_cloud_chat(prompt, temperature)
    elif provider == "nim":
        content = await _nim_chat(prompt, temperature)
    else:
        content = await _ollama_local_chat(prompt)
    return _extract_json(content)
