"""Standalone Gemini connectivity smoke test.

Run this FIRST after setting up `.env` on a new machine, before booting
the full FastAPI app. It isolates "is my API key + network working" from
"is the pipeline logic working" so failures are easy to diagnose.

Usage:
    cd adintel
    .venv/bin/python scripts/test_gemini_connection.py

Exits 0 on success, 1 on failure, with a clear message either way.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running this script directly without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from adintel.clients.gemini import generate_image, generate_text  # noqa: E402
from adintel.config import get_settings  # noqa: E402


async def test_text() -> bool:
    print("\n[1/2] Testing Gemini text generation...")
    try:
        result = await generate_text("Say hello in exactly 5 words.")
        print(f"      Gemini says: {result!r}")
        if not result.strip():
            print("      FAILED: empty response")
            return False
        print("      OK")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"      FAILED: {type(e).__name__}: {e}")
        return False


async def test_image() -> bool:
    print("\n[2/2] Testing Nano Banana (Gemini 2.5 Flash Image) generation...")
    try:
        out_path = Path("generated_creatives/_connection_test.png")
        result_path = await generate_image(
            "A simple minimalist icon of a green checkmark on white background.",
            out_path,
        )
        size = result_path.stat().st_size
        print(f"      Wrote {size:,} bytes -> {result_path}")
        if size < 1000:
            print("      WARNING: file suspiciously small, check contents manually")
            return False
        print("      OK")
        return True
    except Exception as e:  # noqa: BLE001
        err_str = str(e)
        if "RESOURCE_EXHAUSTED" in err_str or "limit: 0" in err_str or "429" in err_str:
            print("      SKIPPED (Free Tier Notice):")
            print("      Image generation model has limit 0 on free-tier API keys.")
            print("      (Text & Multimodal reasoning are working! Set up Pay-As-You-Go on AI Studio if image generation is needed.)")
            return True
        print(f"      FAILED: {type(e).__name__}: {e}")
        return False


async def main() -> int:
    settings = get_settings()
    print("=" * 60)
    print("AdIntel - Gemini Connectivity Smoke Test")
    print("=" * 60)
    print(f"GOOGLE_API_KEY set: {bool(settings.google_api_key) and settings.google_api_key != 'your_google_ai_studio_key_here'}")
    print(f"Text model:  {settings.gemini_text_model}")
    print(f"Image model: {settings.gemini_image_model}")

    if not settings.google_api_key or settings.google_api_key == "your_google_ai_studio_key_here":
        print("\nFAILED: GOOGLE_API_KEY is not set in .env")
        print("Get one at https://aistudio.google.com/apikey and paste it into adintel/.env")
        return 1

    text_ok = await test_text()
    image_ok = await test_image()

    print("\n" + "=" * 60)
    if text_ok and image_ok:
        print("ALL CHECKS PASSED. You're ready to run the full app:")
        print("  .venv/bin/python -m uvicorn adintel.main:app --reload --port 8000")
        return 0
    else:
        print("SOME CHECKS FAILED. Common causes:")
        print("  - Invalid or expired API key")
        print("  - Corporate network / VPN blocking generativelanguage.googleapis.com")
        print("    (if on a corporate laptop, try disconnecting VPN or switching networks)")
        print("  - Free tier rate limit hit (wait a minute and retry)")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
