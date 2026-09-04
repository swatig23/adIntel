"""LongevityAgent — flags ads that Meta's auction has kept alive long enough
to be considered 'proven winners'. No LLM needed; just date math.

Rationale: Meta only keeps ads running if they perform against auction
economics. An ad running >90 days without being paused is a strong signal
the advertiser is profiting.
"""

from __future__ import annotations

from loguru import logger

from ..models import Ad, Competitor


class LongevityAgent:
    def __init__(self, winner_threshold_days: int = 90):
        self.winner_threshold_days = winner_threshold_days

    def run(self, competitors: list[Competitor], min_winners: int = 3) -> list[Ad]:
        all_ads: list[Ad] = []
        for c in competitors:
            all_ads.extend(c.ads)

        # 1. Primary strict filter: running >= threshold days AND active (no stop date)
        winners: list[Ad] = [
            ad for ad in all_ads
            if ad.days_running >= self.winner_threshold_days and ad.delivery_stop is None
        ]

        # 2. Resilient Fallback for historical/political/stub datasets where stop dates exist
        if len(winners) < min_winners and all_ads:
            logger.info(
                f"[LongevityAgent] strict active filter yielded {len(winners)} ads; "
                f"falling back to top longest-running ads across all {len(all_ads)} competitor ads"
            )
            # Sort by days_running descending
            sorted_ads = sorted(all_ads, key=lambda a: a.days_running, reverse=True)
            # Pick top ads running at least 14 days
            fallback = [a for a in sorted_ads if a.days_running >= 14]
            winners = fallback[:max(min_winners, 10)] if fallback else sorted_ads[:min_winners]

        logger.info(f"[LongevityAgent] flagged {len(winners)} winning ads")
        return winners
