"""Orchestrator — wires the six agents into a sequential pipeline.

Deliberately simple: we favor readability over a heavy framework here.
Wrap in ADK's SequentialAgent later if you want the framework's tracing.
"""

from __future__ import annotations

import asyncio

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

        # 1. Ingest — competitors + user brand (parallel inside, no LLM)
        all_brands = [request.user_brand] + request.competitors
        all_competitors = await self.ingest.run(all_brands)
        user_competitor = all_competitors[0]
        competitors = all_competitors[1:]

        # 2. Longevity filter — winners across competitors only (no LLM)
        winners = self.longevity.run(competitors)

        # 3. Analyze — extract patterns from winners (LLM call)
        logger.info("[Orchestrator] calling AnalyzeAgent...")
        patterns = await self.analyze.run(winners)

        # 4 & 5. Gap & Create — run concurrently after patterns are extracted (LLM calls in parallel)
        logger.info("[Orchestrator] running GapAgent and CreateAgent concurrently...")
        gap_coro = self.gap.run(user_competitor.ads, patterns)
        if request.generate_creatives:
            create_coro = self.create.run(
                brand=request.user_brand,
                industry=request.industry_hint or "consumer",
                patterns=patterns,
            )
            gaps, creatives = await asyncio.gather(gap_coro, create_coro)
        else:
            gaps = await gap_coro
            creatives = []

        # 6. Report — narrative summary (LLM call)
        logger.info("[Orchestrator] calling ReportAgent...")
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
