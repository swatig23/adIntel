"""IngestAgent — fetches ads for every competitor (+ optionally the user brand).

Delegates to :mod:`clients.ads` which routes to the configured backend
(meta stub / meta live / BigQuery political / BigQuery Kaggle).
"""

from __future__ import annotations

import asyncio

from loguru import logger

from ..clients.ads import fetch_ads_for_brand
from ..models import Competitor


class IngestAgent:
    """Pulls fresh ads for a set of brand names in parallel."""

    def __init__(self, per_brand_limit: int = 25):
        self.per_brand_limit = per_brand_limit

    async def run(self, brand_names: list[str]) -> list[Competitor]:
        logger.info(f"[IngestAgent] fetching ads for {len(brand_names)} brands")

        async def _one(name: str) -> Competitor:
            try:
                ads = await fetch_ads_for_brand(name, limit=self.per_brand_limit)
            except Exception as e:  # noqa: BLE001
                logger.error(f"[IngestAgent] fetch failed for '{name}': {e}")
                ads = []
            logger.info(f"  ↳ {name}: {len(ads)} ads")
            return Competitor(name=name, ads=ads)

        return await asyncio.gather(*(_one(n) for n in brand_names))
