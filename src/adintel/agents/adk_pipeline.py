"""ADK wrapper — exposes the AdIntel pipeline as a Google ADK
:class:`SequentialAgent` composed of six :class:`BaseAgent` subclasses.

This is the canonical multi-agent architecture for the hackathon submission.
The functional Orchestrator in :mod:`orchestrator` remains available as a
fallback; the ADK path is exposed via :func:`build_adk_pipeline` and
:func:`run_via_adk` and is what the FastAPI app drives by default (see
``ADK_ENABLED`` in :mod:`config`).

Each wrapper reads inputs from ``ctx.session.state`` and writes outputs back
to the same state dict, so the pipeline stays purely declarative.

State keys:
    request                  -> AnalysisRequest
    all_competitors          -> list[Competitor]  (user + peers)
    user_competitor          -> Competitor
    competitors              -> list[Competitor]  (peers only)
    winners                  -> list[Ad]
    patterns                 -> list[Pattern]
    gaps                     -> list[GapItem]
    creatives                -> list[GeneratedCreative]
    executive_summary        -> str
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.runners import InMemoryRunner
from google.genai import types as genai_types
from loguru import logger

from ..models import AnalysisReport, AnalysisRequest
from .analyze import AnalyzeAgent
from .create import CreateAgent
from .gap import GapAgent
from .ingest import IngestAgent
from .longevity import LongevityAgent
from .report import ReportAgent

# Free-tier Gemini rate limits (~5 RPM) mean back-to-back LLM-calling nodes
# need a breather between them. Keep this in sync with the equivalent pause
# in orchestrator.py -- if you tune one, tune the other.
INTER_STAGE_PAUSE_SECONDS = 2

# Keep these in sync with Orchestrator's agent construction args -- both
# were tuned down from higher defaults to respect free-tier quota limits.
INGEST_PER_BRAND_LIMIT = 25
ANALYZE_MAX_IMAGES = 3


def _done_event(author: str, deltas: dict) -> Event:
    """Standard 'this agent finished, here are its state deltas' event."""
    return Event(
        author=author,
        actions=EventActions(state_delta=deltas),
    )


# --- Wrappers --------------------------------------------------------------


class IngestNode(BaseAgent):
    """ADK wrapper around IngestAgent."""

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        req: AnalysisRequest = state["request"]
        ingest = IngestAgent(per_brand_limit=INGEST_PER_BRAND_LIMIT)
        all_brands = [req.user_brand] + req.competitors
        all_comp = await ingest.run(all_brands)
        deltas = {
            "all_competitors": all_comp,
            "user_competitor": all_comp[0],
            "competitors": all_comp[1:],
        }
        state.update(deltas)
        yield _done_event(self.name, deltas)


class LongevityNode(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        winners = LongevityAgent(winner_threshold_days=90).run(state["competitors"])
        state["winners"] = winners
        yield _done_event(self.name, {"winners": winners, "winners_count": len(winners)})


class AnalyzeNode(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        winners = state["winners"]
        patterns = await AnalyzeAgent(
            max_images=ANALYZE_MAX_IMAGES, top_k_patterns=6
        ).run(winners)
        state["patterns"] = patterns
        yield _done_event(self.name, {"patterns": patterns, "patterns_count": len(patterns)})
        # AnalyzeAgent short-circuits (no Gemini call) when there are no
        # winning ads -- skip the rate-limit pause too in that case, since
        # there's no quota to protect and no reason to make the user wait.
        if winners:
            await asyncio.sleep(INTER_STAGE_PAUSE_SECONDS)


class GapNode(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        user = state["user_competitor"]
        patterns = state["patterns"]
        gaps = await GapAgent().run(user.ads, patterns)
        state["gaps"] = gaps
        yield _done_event(self.name, {"gaps": gaps, "gaps_count": len(gaps)})
        # GapAgent short-circuits (no Gemini call) when there are no
        # patterns to compare against -- same reasoning as AnalyzeNode.
        if patterns:
            await asyncio.sleep(INTER_STAGE_PAUSE_SECONDS)


class CreateNode(BaseAgent):
    model_config = {"arbitrary_types_allowed": True}

    output_dir: Path = Path("generated_creatives")
    n_creatives: int = 3

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        req: AnalysisRequest = state["request"]
        if not req.generate_creatives:
            state["creatives"] = []
            yield _done_event(self.name, {"creatives": [], "skipped": True})
            return

        creator = CreateAgent(output_dir=self.output_dir, n_creatives=self.n_creatives)
        patterns = state["patterns"]
        creatives = await creator.run(
            brand=req.user_brand,
            industry=req.industry_hint or "consumer",
            patterns=patterns,
        )
        state["creatives"] = creatives
        yield _done_event(self.name, {"creatives": creatives, "creatives_count": len(creatives)})
        # CreateAgent short-circuits (no Gemini call) when there are no
        # patterns to draw inspiration from -- same reasoning as above.
        if patterns:
            await asyncio.sleep(INTER_STAGE_PAUSE_SECONDS)


class ReportNode(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        req: AnalysisRequest = state["request"]
        summary = await ReportAgent().run(
            brand=req.user_brand,
            competitors=state["competitors"],
            patterns=state["patterns"],
            gaps=state["gaps"],
            winner_count=len(state["winners"]),
        )
        state["executive_summary"] = summary
        yield _done_event(self.name, {"executive_summary": summary})


# --- Assembly ----------------------------------------------------------


def build_adk_pipeline(
    creative_output_dir: Path = Path("generated_creatives"),
) -> SequentialAgent:
    """Compose the six agents into a single ADK SequentialAgent."""
    return SequentialAgent(
        name="adintel_pipeline",
        description=(
            "AdIntel: pulls competitor ads, flags proven winners, extracts "
            "cross-ad patterns with Gemini, identifies user gaps, generates "
            "fresh creatives with Nano Banana, and writes an executive summary."
        ),
        sub_agents=[
            IngestNode(name="ingest"),
            LongevityNode(name="longevity"),
            AnalyzeNode(name="analyze"),
            GapNode(name="gap"),
            CreateNode(name="create", output_dir=creative_output_dir),
            ReportNode(name="report"),
        ],
    )


async def run_via_adk(
    request: AnalysisRequest,
    creative_output_dir: Path = Path("generated_creatives"),
) -> AnalysisReport:
    """Runs the ADK pipeline end-to-end and returns a typed report."""
    pipeline = build_adk_pipeline(creative_output_dir=creative_output_dir)
    runner = InMemoryRunner(agent=pipeline, app_name="adintel")

    # Seed initial state at session-creation time (persisted correctly)
    session = await runner.session_service.create_session(
        app_name="adintel",
        user_id="hackathon-user",
        state={"request": request},
    )

    logger.info("[ADK] running SequentialAgent adintel_pipeline")
    async for event in runner.run_async(
        user_id="hackathon-user",
        session_id=session.id,
        new_message=genai_types.Content(
            parts=[genai_types.Part(text=f"Analyze {request.user_brand}")]
        ),
    ):
        logger.debug(f"[ADK] event from {event.author}")

    final = await runner.session_service.get_session(
        app_name="adintel",
        user_id="hackathon-user",
        session_id=session.id,
    )
    state = final.state

    return AnalysisReport(
        request=request,
        competitors=state["competitors"],
        patterns=state["patterns"],
        gaps=state["gaps"],
        generated_creatives=state.get("creatives", []),
        executive_summary=state["executive_summary"],
        winner_ad_ids=[a.id for a in state["winners"]],
    )
