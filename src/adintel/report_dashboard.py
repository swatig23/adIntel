"""Dashboard-ready derived data for AnalysisReport.

Product-design rationale: a marketer reviewing this report wants a
5-second visual scan (headline + a couple of charts), not paragraphs of
prose. Full text detail (the LLM's narrative, per-pattern descriptions,
per-gap recommendations) stays available -- just tucked behind
progressive-disclosure <details> elements in the UI instead of being the
first thing on the page.

This logic lives in its own module (not on AnalysisReport itself) to keep
the Pydantic model focused on being a data container, and this file
focused on presentation-prep. Small, unit-testable, no Jinja needed.
"""

from __future__ import annotations

import re

from .models import AnalysisReport


def extract_headline(executive_summary: str) -> str:
    """Pulls just the one-sentence headline out of ReportAgent's markdown
    output (see agents/report.py's PROMPT, section 1 "**Headline**").

    Falls back to the first non-empty line if the expected markdown
    structure isn't present, so this never crashes on unexpected LLM
    output -- it just degrades gracefully to *something* reasonable.
    """
    match = re.search(
        r"\*\*Headline\*\*\s*\n+(.+?)(?:\n\n|\n\*\*|$)",
        executive_summary,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    for line in executive_summary.splitlines():
        stripped = line.strip().lstrip("*").strip()
        if stripped:
            return stripped
    return ""


def pattern_chart_data(report: AnalysisReport) -> dict:
    """Labels + frequency values for the winning-patterns bar chart."""
    return {
        "labels": [p.category.replace("_", " ").title() for p in report.patterns],
        "data": [round(p.frequency_pct, 1) for p in report.patterns],
    }


def gap_coverage_chart_data(report: AnalysisReport) -> dict:
    """Already-doing vs gap-detected counts for the coverage donut chart."""
    has = sum(1 for g in report.gaps if g.user_has)
    missing = len(report.gaps) - has
    return {"labels": ["Already Doing", "Gap Detected"], "data": [has, missing]}


def competitor_chart_data(report: AnalysisReport) -> dict:
    """Ads-analyzed vs proven-winners per competitor, for a grouped bar
    chart -- replaces what used to be a plain text list of numbers."""
    return {
        "labels": [c.name for c in report.competitors],
        "ads": [len(c.ads) for c in report.competitors],
        "winners": [len(report.winners_for(c)) for c in report.competitors],
    }
