"""Orchestrator — wires the six agents into a sequential pipeline.

Deliberately simple: we favor readability over a heavy framework here.
Wrap in ADK's SequentialAgent later if you want the framework's tracing.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from ..models import AnalysisReport, AnalysisRequest
from .analyze import AnalyzeAgent
from .create import CreateAgent
from .gap import GapAgent
from .ingest import IngestAgent
from .longevity import LongevityAgent
from .report import ReportAgent


class Orchestrator:
    """Runs the full AdIntel pipeline end-to-end."""

    def __init__(self, creative_output_dir: Path = Path("generated_creatives")):
        self.ingest = IngestAgent(per_brand_limit=25)
        self.longevity = LongevityAgent(winner_threshold_days=90)
        self.analyze = AnalyzeAgent(max_images=10, top_k_patterns=6)
        self.gap = GapAgent()
        self.create = CreateAgent(output_dir=creative_output_dir, n_creatives=3)
        self.report = ReportAgent()

    async def run(self, request: AnalysisRequest) -> AnalysisReport:
        logger.info(f"[Orchestrator] starting run for '{request.user_brand}'")

        # 1. Ingest — competitors + user brand (parallel inside)
        all_brands = [request.user_brand] + request.competitors
        all_competitors = await self.ingest.run(all_brands)
        user_competitor = all_competitors[0]
        competitors = all_competitors[1:]

        # 2. Longevity filter — winners across competitors only
        winners = self.longevity.run(competitors)

        # 3. Analyze — extract patterns from winners
        patterns = await self.analyze.run(winners)

        # 4. Gap — compare user's ads vs patterns
        gaps = await self.gap.run(user_competitor.ads, patterns)

        # 5. Create — new creatives (optional, gated by request flag)
        creatives = []
        if request.generate_creatives:
            creatives = await self.create.run(
                brand=request.user_brand,
                industry=request.industry_hint or "consumer",
                patterns=patterns,
            )

        # 6. Report — narrative summary
        summary = await self.report.run(
            brand=request.user_brand,
            competitors=competitors,
            patterns=patterns,
            gaps=gaps,
        )

        logger.info("[Orchestrator] done")
        return AnalysisReport(
            request=request,
            competitors=competitors,
            patterns=patterns,
            gaps=gaps,
            generated_creatives=creatives,
            executive_summary=summary,
        )
