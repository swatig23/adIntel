"""Thin wrapper around google-genai for text, vision, and image generation.

Keeps the rest of the codebase from caring about SDK details.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types as genai_types
from loguru import logger

from ..config import get_settings

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.google_api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Get one at https://aistudio.google.com/apikey"
            )
        _client = genai.Client(api_key=settings.google_api_key)
    return _client


async def generate_text(prompt: str, *, system: Optional[str] = None) -> str:
    """One-shot text generation with Gemini."""
    settings = get_settings()
    client = _get_client()

    def _call() -> str:
        cfg = genai_types.GenerateContentConfig(system_instruction=system) if system else None
        resp = client.models.generate_content(
            model=settings.gemini_text_model,
            contents=prompt,
            config=cfg,
        )
        return (resp.text or "").strip()

    return await asyncio.to_thread(_call)


async def generate_from_multimodal(
    prompt: str,
    image_urls: list[str],
    *,
    system: Optional[str] = None,
) -> str:
    """Text generation grounded in one or more image URLs."""
    import httpx

    settings = get_settings()
    client = _get_client()

    # Fetch bytes in parallel (cheap for the stub; polite for live URLs)
    async with httpx.AsyncClient(timeout=20) as http:
        results = await asyncio.gather(
            *(http.get(u) for u in image_urls), return_exceptions=True
        )

    parts: list = [prompt]
    for r, url in zip(results, image_urls):
        if isinstance(r, Exception) or getattr(r, "status_code", 500) >= 400:
            logger.warning(f"Skipping image {url}: {r}")
            continue
        parts.append(
            genai_types.Part.from_bytes(
                data=r.content,
                mime_type=r.headers.get("content-type", "image/jpeg"),
            )
        )

    def _call() -> str:
        cfg = genai_types.GenerateContentConfig(system_instruction=system) if system else None
        resp = client.models.generate_content(
            model=settings.gemini_vision_model,
            contents=parts,
            config=cfg,
        )
        return (resp.text or "").strip()

    return await asyncio.to_thread(_call)


async def generate_image(prompt: str, output_path: Path) -> Path:
    """Generate an image via Gemini 2.5 Flash Image ('Nano Banana').

    Writes PNG bytes to ``output_path`` and returns the path.
    """
    settings = get_settings()
    client = _get_client()

    def _call() -> bytes:
        resp = client.models.generate_content(
            model=settings.gemini_image_model,
            contents=prompt,
        )
        # Walk candidates → parts → inline_data.data (bytes)
        for cand in resp.candidates or []:
            for part in getattr(cand.content, "parts", []) or []:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    return inline.data
        raise RuntimeError("Gemini did not return any image bytes")

    data = await asyncio.to_thread(_call)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    logger.info(f"Wrote generated image → {output_path}")
    return output_path
