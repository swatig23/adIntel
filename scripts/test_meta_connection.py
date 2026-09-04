"""Standalone Meta Ad Library API connectivity smoke test.

Run this BEFORE flipping DATA_SOURCE=meta_live in .env. It isolates
"is my access token valid + has the right permission" from "is the
pipeline logic working", so failures are easy to diagnose without
needing to paste a secret token anywhere.

Usage:
    cd adintel
    .venv/bin/python scripts/test_meta_connection.py
    .venv/bin/python scripts/test_meta_connection.py "Some Brand"

Exits 0 on success, 1 on failure, with a clear message either way.
Never prints the token itself.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from adintel.config import get_settings  # noqa: E402


def check_settings() -> bool:
    print("[1/3] Checking configuration...")
    settings = get_settings()
    if not settings.meta_access_token:
        print("      FAILED: META_ACCESS_TOKEN is not set in .env")
        print("      Get one via https://developers.facebook.com/tools/explorer/")
        return False
    # Never print the token itself -- just prove it's present and roughly
    # the right shape (Meta tokens are long strings, usually 100+ chars).
    token_len = len(settings.meta_access_token)
    print(f"      META_ACCESS_TOKEN: set ({token_len} characters)")
    if token_len < 40:
        print("      WARNING: token looks unusually short -- did the copy-paste get truncated?")
    print("      OK")
    return True


async def check_live_call(brand_override: str | None = None) -> bool:
    print("\n[2/3] Testing a real Ad Library API call...")
    try:
        from adintel.clients.meta_ads import _fetch_live_ads

        brand = brand_override or "Nike"
        print(f"      Querying Ad Library for '{brand}'...")
        ads = await _fetch_live_ads(brand, limit=5)
        print(f"      Got {len(ads)} ads back")

        if not ads:
            print(f"      WARNING: 0 ads for '{brand}'. This can mean either:")
            print("        - the token/call worked fine but this brand has no active/archived ads")
            print("        - try a different well-known brand, e.g.:")
            print('          .venv/bin/python scripts/test_meta_connection.py "Temu"')
            return False

        sample = ads[0]
        print(f"      Sample ad: page_name={sample.page_name!r}")
        print(f"      Sample body_text: {sample.body_text[:120]!r}")
        if not sample.body_text.strip():
            print("      WARNING: body_text is empty for this ad (common for video/image-only ads)")
            print("      Try another brand or increase limit -- not every ad has text.")
        print("      OK")
        return True
    except Exception as e:  # noqa: BLE001
        err = str(e)
        print(f"      FAILED: {type(e).__name__}: {err}")
        if "OAuth" in err or "access token" in err.lower():
            print("      -> Token is invalid or expired. Regenerate it at:")
            print("         https://developers.facebook.com/tools/explorer/")
        elif "permission" in err.lower() or "(#200)" in err:
            print("      -> Missing 'ads_read' permission. Add it in Graph API")
            print("         Explorer's permissions dropdown, then regenerate the token.")
        return False


def check_data_source_setting() -> bool:
    print("\n[3/3] Checking DATA_SOURCE setting...")
    settings = get_settings()
    print(f"      Current DATA_SOURCE: {settings.data_source}")
    if settings.data_source != "meta_live":
        print("      NOTE: DATA_SOURCE is not yet 'meta_live' -- the app will still")
        print(f"      use '{settings.data_source}' until you update .env.")
        return False
    print("      OK - app is configured to use live Meta data")
    return True


async def main() -> int:
    print("=" * 60)
    print("AdIntel - Meta Ad Library Connectivity Smoke Test")
    print("=" * 60)

    brand_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if not check_settings():
        return 1

    call_ok = await check_live_call(brand_arg)
    source_ok = check_data_source_setting()

    print("\n" + "=" * 60)
    if call_ok and source_ok:
        print("ALL CHECKS PASSED. Restart your server and try a real /analyze run.")
        return 0
    elif call_ok and not source_ok:
        print("Token works! Just set DATA_SOURCE=meta_live in .env and restart.")
        return 0
    else:
        print("SOME CHECKS FAILED. Fix the issue above before flipping")
        print("DATA_SOURCE=meta_live, or stay on DATA_SOURCE=meta_stub for now.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
