"""Test Meta Ad Library API connectivity with the user's META_ACCESS_TOKEN.

Run:
    uv run python scripts/test_meta_connection.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from dotenv import load_dotenv
import httpx

load_dotenv()

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "").strip()
META_API_BASE = "https://graph.facebook.com/v18.0/ads_archive"


async def main():
    print("=" * 60)
    print("AdIntel - Meta Ad Library API Token Verification")
    print("=" * 60)

    if not META_ACCESS_TOKEN:
        print("❌ ERROR: META_ACCESS_TOKEN is not set in .env")
        print("   Please paste your token into .env:")
        print("   META_ACCESS_TOKEN=EAAB...")
        sys.exit(1)

    print(f"Token found (prefix: {META_ACCESS_TOKEN[:10]}...)")
    print("\nTesting Meta Ad Library search for 'Nike'...")

    params = {
        "search_terms": "Nike",
        "ad_reached_countries": "['US']",
        "ad_active_status": "ALL",
        "limit": 5,
        "fields": "id,page_id,page_name,ad_delivery_start_time,ad_snapshot_url",
        "access_token": META_ACCESS_TOKEN,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(META_API_BASE, params=params)
            if r.status_code == 200:
                data = r.json().get("data", [])
                print(f"✅ SUCCESS! Connected to Meta Ad Library API.")
                print(f"   Received {len(data)} sample ads for 'Nike'.")
                if data:
                    print(f"   Sample Ad ID: {data[0].get('id')} (Page: {data[0].get('page_name')})")
                print("\nTo use Meta live API in AdIntel, configure .env with:")
                print("   DATA_SOURCE=meta_live")
                print("   USE_META_STUB=false")
            else:
                raw_json = r.json()
                err = raw_json.get("error", {})
                print(f"❌ API ERROR ({r.status_code}): {err.get('message')}")
                print(f"   Full Error Payload: {raw_json}")
                if err.get("code") in (10, 200):
                    print("\n💡 META POLICY REQUIREMENT:")
                    print("   Meta requires 'Identity & Location Verification' on your Facebook Developer Account")
                    print("   before granting live access to the /ads_archive API endpoint.")
                    print("   Verification takes Meta 1-3 days to process (ID card / Passport upload).")
        except Exception as e:
            print(f"❌ HTTP/NETWORK ERROR: {e}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
