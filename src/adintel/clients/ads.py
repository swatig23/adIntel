"""Ad-source dispatcher.

Given a brand/advertiser name, returns a list of :class:`Ad` from whichever
backend is configured via ``DATA_SOURCE`` env var.

Backends supported:

* ``meta_stub``    \u2014 :func:`clients.meta_ads.fetch_ads_for_brand` (default)
* ``meta_live``    \u2014 same module, live API mode (needs META_ACCESS_TOKEN)
* ``bq_political``          \u2014 :func:`clients.bq_ads.fetch_political_ads_for_advertiser`
* ``bq_kaggle``             \u2014 :func:`clients.bq_ads.fetch_kaggle_ads_for_advertiser` (generic, tolerant)
* ``bq_kaggle_transcripts`` \u2014 :func:`clients.bq_ads.fetch_transcripts_ads_for_advertiser`
  (exact schema for the 'Advertisement Transcripts from Various
  Industries' dataset -- real commercial ad copy, 1348 brands, no dates)

All backends return identical ``list[Ad]`` shape so downstream agents
never need to care which source was used.
"""

from __future__ import annotations

from loguru import logger

from ..config import get_settings
from ..models import Ad
from . import bq_ads, curated_visual, meta_ads

_VALID_SOURCES = {"meta_stub", "meta_live", "bq_political", "bq_kaggle", "bq_kaggle_transcripts", "curated_visual"}


async def fetch_ads_for_brand(brand: str, limit: int | None = None) -> list[Ad]:
    """Route to the configured backend and return a list of Ads."""
    settings = get_settings()
    source = (settings.data_source or "meta_stub").strip().lower()

    if source not in _VALID_SOURCES:
        logger.warning(f"[ads:dispatcher] unknown DATA_SOURCE='{source}', falling back to meta_stub")
        source = "meta_stub"

    if source == "meta_stub":
        # Preserve the historical behaviour: meta_ads client picks its own
        # stub vs live based on USE_META_STUB regardless of this dispatcher.
        return await meta_ads.fetch_ads_for_brand(brand, limit=limit or 25)

    if source == "meta_live":
        # Force-disable stub for this branch so the live path is used even
        # if USE_META_STUB=true in .env (safer default for other branches).
        original = settings.use_meta_stub
        settings.use_meta_stub = False
        try:
            return await meta_ads.fetch_ads_for_brand(brand, limit=limit or 25)
        finally:
            settings.use_meta_stub = original

    if source == "bq_political":
        return await bq_ads.fetch_political_ads_for_advertiser(
            brand, limit=limit or settings.bq_limit_per_brand
        )

    if source == "bq_kaggle":
        return await bq_ads.fetch_kaggle_ads_for_advertiser(
            brand, limit=limit or settings.bq_limit_per_brand
        )

    if source == "bq_kaggle_transcripts":
        return await bq_ads.fetch_transcripts_ads_for_advertiser(
            brand, limit=limit or settings.bq_limit_per_brand
        )

    if source == "curated_visual":
        return await curated_visual.fetch_curated_visual_ads(
            brand, limit=limit or settings.bq_limit_per_brand
        )

    # Unreachable given the guard above, but keeps type-checkers happy.
    return []
