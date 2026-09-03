"""Smoke test: pipeline runs end-to-end in stub mode without touching Gemini.

Useful as a wiring check before you plug in real API keys.
"""

from __future__ import annotations

import asyncio
import os

# Force stub mode before importing anything that reads settings
os.environ["USE_META_STUB"] = "true"
os.environ.setdefault("GOOGLE_API_KEY", "test-placeholder")

from adintel.agents.ingest import IngestAgent  # noqa: E402
from adintel.agents.longevity import LongevityAgent  # noqa: E402


def test_ingest_returns_ads():
    async def _run():
        ingest = IngestAgent(per_brand_limit=15)
        result = await ingest.run(["Warby Parker", "Ray-Ban"])
        assert len(result) == 2
        assert all(len(c.ads) == 15 for c in result)
        return result

    competitors = asyncio.run(_run())
    assert competitors[0].name == "Warby Parker"


def test_longevity_filters_winners():
    async def _fetch():
        return await IngestAgent(per_brand_limit=30).run(["Ray-Ban"])

    competitors = asyncio.run(_fetch())
    winners = LongevityAgent(winner_threshold_days=90).run(competitors)
    # Stub generates a mix; at least some should be winners across 30 ads
    assert isinstance(winners, list)
    for w in winners:
        assert w.days_running >= 90
        assert w.delivery_stop is None


def test_stub_is_deterministic():
    """Same brand name should yield the same ads across runs."""
    async def _fetch():
        r1 = await IngestAgent(per_brand_limit=10).run(["Warby Parker"])
        r2 = await IngestAgent(per_brand_limit=10).run(["Warby Parker"])
        return r1, r2

    a, b = asyncio.run(_fetch())
    assert [ad.id for ad in a[0].ads] == [ad.id for ad in b[0].ads]
