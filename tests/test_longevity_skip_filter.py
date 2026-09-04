"""Tests for LongevityAgent's BQ_SKIP_LONGEVITY_FILTER escape hatch.

Some data sources (bq_kaggle_transcripts) have no delivery-date columns
at all. Without this flag, every ad would compute days_running=0 and
get silently filtered out, leaving the pipeline with zero winners and
zero downstream analysis -- a confusing empty-result bug, not an error.
"""

from __future__ import annotations

import os

os.environ.setdefault("GOOGLE_API_KEY", "test-placeholder")

from datetime import datetime, timezone

from adintel.agents.longevity import LongevityAgent
from adintel.config import get_settings
from adintel.models import Ad, Competitor, CreativeType


def _dateless_ad(page_name: str) -> Ad:
    """An ad shaped like one from bq_kaggle_transcripts: no real dates,
    delivery_start defaults to now() so days_running is always 0."""
    return Ad(
        id=f"id-{page_name}",
        page_name=page_name,
        page_id=f"pid-{page_name}",
        creative_type=CreativeType.TEXT,
        body_text=f"Ad copy for {page_name}",
        delivery_start=datetime.now(timezone.utc),
        delivery_stop=None,
    )


def test_default_behaviour_filters_out_dateless_ads():
    """Sanity check: WITHOUT the flag, dateless ads (days_running=0)
    are correctly excluded by the normal 90-day filter."""
    get_settings.cache_clear()
    os.environ.pop("BQ_SKIP_LONGEVITY_FILTER", None)
    get_settings.cache_clear()

    competitors = [Competitor(name="BMW", ads=[_dateless_ad("BMW"), _dateless_ad("BMW")])]
    winners = LongevityAgent(winner_threshold_days=90).run(competitors)
    assert winners == []  # confirms the bug this flag exists to prevent


def test_skip_filter_treats_all_ads_as_winners():
    """WITH the flag set, every fetched ad should pass through untouched,
    regardless of days_running."""
    os.environ["BQ_SKIP_LONGEVITY_FILTER"] = "true"
    get_settings.cache_clear()
    try:
        assert get_settings().bq_skip_longevity_filter is True

        ads = [_dateless_ad("BMW"), _dateless_ad("BMW"), _dateless_ad("Audi")]
        competitors = [Competitor(name="BMW", ads=ads[:2]), Competitor(name="Audi", ads=ads[2:])]
        winners = LongevityAgent(winner_threshold_days=90).run(competitors)
        assert len(winners) == 3
    finally:
        os.environ.pop("BQ_SKIP_LONGEVITY_FILTER", None)
        get_settings.cache_clear()
