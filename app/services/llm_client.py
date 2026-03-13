from __future__ import annotations

import json

import httpx

from app.core.config import settings


def generate_with_glm(
    messages: list[dict],
    *,
    timeout_seconds: int | None = None,
    temperature: float = 0.2,
    max_tokens: int = 360,
) -> str | None:
    """Call GLM (OpenAI-compatible chat completions). Return None on any failure."""
    if settings.llm_provider.lower() != "glm":
        return None
    if not settings.llm_api_key:
        return None

    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        timeout = timeout_seconds or settings.llm_timeout_seconds
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, content=json.dumps(payload, ensure_ascii=False))
            resp.raise_for_status()
            data = resp.json()
        message = data["choices"][0]["message"]
        content = (message.get("content") or "").strip()
        return content or None
    except Exception:
        return None
