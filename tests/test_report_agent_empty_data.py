"""ReportAgent should never burn a Gemini call summarizing zero ads.

Before this fix, a brand with no matches in the data source (e.g. a Kaggle
transcripts miss) still triggered a full LLM call to "summarize" nothing --
wasting quota on output nobody needed. See agents/report.py's short-circuit.
"""

from __future__ import annotations

import os

os.environ.setdefault("GOOGLE_API_KEY", "test-placeholder")

import pytest

from adintel.agents import report as report_module
from adintel.agents.report import ReportAgent
from adintel.models import Competitor


@pytest.mark.asyncio
async def test_skips_gemini_call_when_no_ads_at_all(monkeypatch):
    called = False

    async def _fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("generate_text should not be called with 0 ads")

    monkeypatch.setattr(report_module, "generate_text", _fail_if_called)

    competitors = [Competitor(name="Tarzan", ads=[]), Competitor(name="RayBan", ads=[])]
    summary = await ReportAgent().run(
        brand="Acme",
        competitors=competitors,
        patterns=[],
        gaps=[],
        winner_count=0,
    )

    assert called is False
    assert "Tarzan" in summary
    assert "RayBan" in summary
    assert "No ads were found" in summary


@pytest.mark.asyncio
async def test_calls_gemini_when_at_least_one_ad_exists(monkeypatch):
    called_with = {}

    async def _fake_generate_text(prompt, *, system=None):
        called_with["prompt"] = prompt
        return "**Headline**\nSomething real."

    monkeypatch.setattr(report_module, "generate_text", _fake_generate_text)

    from adintel.models import Ad, CreativeType
    from datetime import datetime, timezone

    ad = Ad(
        id="a1",
        page_name="BMW",
        page_id="p1",
        creative_type=CreativeType.TEXT,
        body_text="copy",
        delivery_start=datetime.now(timezone.utc),
    )
    competitors = [Competitor(name="BMW", ads=[ad])]
    summary = await ReportAgent().run(
        brand="Acme",
        competitors=competitors,
        patterns=[],
        gaps=[],
        winner_count=0,
    )

    assert called_with  # generate_text WAS called
    assert summary == "**Headline**\nSomething real."
