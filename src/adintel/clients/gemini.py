"""Thin wrapper around google-genai for text, vision, and image generation.

Keeps the rest of the codebase from caring about SDK details.

Includes automatic retry with exponential backoff for free-tier rate limits
(5 requests/minute on gemini-3.6-flash).
"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types as genai_types
from loguru import logger

from ..config import get_settings

_client: Optional[genai.Client] = None

# Rate-limit aware retry settings
MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 15  # free tier = 5 RPM, so ~12s between calls is safe


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


def _extract_retry_delay(error_msg: str) -> float:
    """Try to parse the server-suggested retry delay from a 429 error message."""
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_msg, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return BASE_BACKOFF_SECONDS


FALLBACK_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
]


def _call_with_retry(call_fn, primary_model: str, label: str = "Gemini"):
    """Call model with instant fallback to alternative available models on 503/429 errors."""
    models_to_try = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]
    last_err = None

    for model_name in models_to_try:
        for attempt in range(1, 3):
            try:
                return call_fn(model_name)
            except Exception as e:
                err_str = str(e)
                is_rate_limit = "RESOURCE_EXHAUSTED" in err_str or "429" in err_str
                is_transient = (
                    "503" in err_str
                    or "UNAVAILABLE" in err_str
                    or "500" in err_str
                    or "502" in err_str
                    or "504" in err_str
                )

                if not (is_rate_limit or is_transient):
                    raise

                last_err = e
                logger.warning(
                    f"[{label}] Model {model_name} busy ({e}); falling back to next candidate model..."
                )
                break  # try next model in candidate list instantly!

    raise last_err or RuntimeError("All candidate Gemini models busy")


async def generate_text(prompt: str, *, system: Optional[str] = None) -> str:
    """One-shot text generation with Gemini."""
    settings = get_settings()
    client = _get_client()

    def _call(model_name: str) -> str:
        cfg = genai_types.GenerateContentConfig(system_instruction=system) if system else None
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=cfg,
        )
        return (resp.text or "").strip()

    return await asyncio.to_thread(
        _call_with_retry, _call, settings.gemini_text_model, "generate_text"
    )


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
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as http:
        results = await asyncio.gather(
            *(http.get(u) for u in image_urls), return_exceptions=True
        )

    parts: list = [prompt]
    for r, url in zip(results, image_urls):
        if isinstance(r, Exception) or getattr(r, "status_code", 500) >= 400:
            logger.warning(f"Skipping image {url}: {r}")
            continue
        raw_mime = r.headers.get("content-type", "image/jpeg")
        mime = raw_mime.split(";")[0].strip()
        if not mime.startswith("image/"):
            logger.warning(f"Skipping non-image mime type '{mime}' for {url}")
            continue
        parts.append(
            genai_types.Part.from_bytes(
                data=r.content,
                mime_type=mime,
            )
        )

    def _call(model_name: str) -> str:
        cfg = genai_types.GenerateContentConfig(system_instruction=system) if system else None
        resp = client.models.generate_content(
            model=model_name,
            contents=parts,
            config=cfg,
        )
        return (resp.text or "").strip()

    return await asyncio.to_thread(
        _call_with_retry, _call, settings.gemini_vision_model, "generate_multimodal"
    )


async def generate_image(prompt: str, output_path: Path) -> Path:
    """Generate an image via Gemini Flash Image ('Nano Banana').

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

    # Image generation on free tier is limit 0; attempt once without long retry loops
    data = await asyncio.to_thread(_call)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    logger.info(f"Wrote generated image → {output_path}")
    return output_path
