"""LongevityAgent — flags ads that Meta's auction has kept alive long enough
to be considered 'proven winners'. No LLM needed; just date math.

Rationale: Meta only keeps ads running if they perform against auction
economics. An ad running >90 days without being paused is a strong signal
the advertiser is profiting.

Some data sources (e.g. bq_kaggle_transcripts, a curated "one notable ad
per brand" dataset) have no delivery dates at all. For those, set
BQ_SKIP_LONGEVITY_FILTER=true so every fetched ad is treated as a winner
instead of being date-filtered into an empty list.
"""

from __future__ import annotations

from loguru import logger

from ..config import get_settings
from ..models import Ad, Competitor


class LongevityAgent:
    def __init__(self, winner_threshold_days: int = 90):
        self.winner_threshold_days = winner_threshold_days

    def run(self, competitors: list[Competitor]) -> list[Ad]:
        if get_settings().bq_skip_longevity_filter:
            winners = [ad for c in competitors for ad in c.ads]
            logger.info(
                f"[LongevityAgent] BQ_SKIP_LONGEVITY_FILTER=true -> "
                f"treating all {len(winners)} ads as winners (no date signal in this source)"
            )
            return winners

        winners: list[Ad] = []
        for c in competitors:
            for ad in c.ads:
                if ad.days_running >= self.winner_threshold_days and ad.delivery_stop is None:
                    winners.append(ad)
        logger.info(f"[LongevityAgent] flagged {len(winners)} winning ads")
        return winners
