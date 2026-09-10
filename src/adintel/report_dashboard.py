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

from .creative_dna import DIMENSIONS, average_dimensions, dominant_signals
from .models import Ad, AnalysisReport


def extract_headline(executive_summary: str) -> str:
    """Pulls just the one-sentence headline out of ReportAgent's markdown
    output (see agents/report.py's PROMPT, section "**Headline**").

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


def extract_strategy_name(executive_summary: str) -> str:
    """Pulls the punchy 2-5 word strategy name out of ReportAgent's markdown
    output (see agents/report.py's PROMPT, section "**Strategy Name**").

    Unlike extract_headline, this has NO fallback to the first line -- a
    stray sentence mistaken for a strategy name would look worse than just
    not showing one. Returns empty string if the section isn't present,
    and the template simply omits the name badge in that case.
    """
    match = re.search(
        r"\*\*Strategy Name\*\*\s*\n+(.+?)(?:\n\n|\n\*\*|$)",
        executive_summary,
        re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def extract_summary_section(executive_summary: str, heading: str) -> str:
    """Generic extractor for any '**Heading**\\n...' block in ReportAgent's
    markdown output (see agents/report.py's PROMPT for the five sections it
    always writes: Strategy Name, Headline, What's working for competitors,
    Your top 3 moves this week, What NOT to do).

    Returns empty string when the heading isn't present -- callers decide
    how to degrade (usually: just omit that block from the expanded view).
    """
    match = re.search(
        rf"\*\*{re.escape(heading)}\*\*\s*\n+(.+?)(?:\n\n\*\*|$)",
        executive_summary,
        re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def top_patterns(report: AnalysisReport, n: int = 3) -> list:
    """The N highest-frequency patterns, for the Biggest Opportunity's
    short evidence bullets. Reuses the same deterministic Pattern records
    charted elsewhere -- no new extraction, no repeated LLM prose."""
    return sorted(report.patterns, key=lambda p: -p.frequency_pct)[:n]


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


def data_quality_summary(report: AnalysisReport) -> dict:
    """Flags brands the data source had zero ads for, so the UI can say so
    explicitly instead of silently rendering a hollow report (empty charts,
    zero patterns, blank executive summary) with no indication of why.

    A brand missing from the underlying dataset is a normal, expected
    outcome for curated sources like the Kaggle transcripts table -- not a
    bug -- but the user still deserves to know it happened.
    """
    zero_ad_brands = [c.name for c in report.competitors if not c.ads]
    total_ads = sum(len(c.ads) for c in report.competitors)
    return {
        "zero_ad_brands": zero_ad_brands,
        "total_ads": total_ads,
        "is_empty": total_ads == 0,
        "is_partial": bool(zero_ad_brands) and total_ads > 0,
    }


def gap_evidence_cards(report: AnalysisReport) -> dict[str, list[dict]]:
    """Resolve each recommendation's validated IDs into render-safe ad cards.

    The returned structure intentionally exposes only information that was
    already part of the public ad record. Missing IDs simply produce no card;
    an old saved report must never fail because a source ad disappeared.
    """
    ads_by_id: dict[str, Ad] = {
        ad.id: ad for competitor in report.competitors for ad in competitor.ads
    }
    cards: dict[str, list[dict]] = {}
    for gap in report.gaps:
        cards[gap.pattern.description] = [
            {
                "id": ad.id,
                "brand": ad.page_name,
                "body_text": ad.body_text[:240],
                "cta": ad.cta,
                "creative_type": ad.creative_type.value.replace("_", " ").title(),
                "days_running": ad.days_running,
                "image_url": ad.image_url,
                "snapshot_url": ad.snapshot_url,
            }
            for ad_id in gap.evidence_ad_ids
            if (ad := ads_by_id.get(ad_id)) is not None
        ]
    return cards


def competitive_scorecard(report: AnalysisReport) -> dict:
    """Compare observable Creative DNA signals, never performance outcomes."""
    dna_by_id = {dna.ad_id: dna for dna in report.creative_dna}
    user_dna = [dna_by_id[ad.id] for ad in report.user_ads if ad.id in dna_by_id]
    competitor_ads = [ad for competitor in report.competitors for ad in report.winners_for(competitor)]
    # Curated sources can legitimately have no measured winner status. In
    # that case compare with the retrieved ads instead of presenting blanks.
    if not competitor_ads:
        competitor_ads = [ad for competitor in report.competitors for ad in competitor.ads]
    competitor_dna = [dna_by_id[ad.id] for ad in competitor_ads if ad.id in dna_by_id]
    user = average_dimensions(user_dna)
    competitors = average_dimensions(competitor_dna)
    rows = [
        {
            "dimension": dimension,
            "user": user[dimension],
            "competitor": competitors[dimension],
            "gap": round(user[dimension] - competitors[dimension], 1),
        }
        for dimension in DIMENSIONS
    ]
    user_total = round(sum(user.values()) / len(DIMENSIONS) * 10) if user_dna else 0
    competitor_total = round(sum(competitors.values()) / len(DIMENSIONS) * 10) if competitor_dna else 0
    by_brand: dict[str, list] = {}
    for competitor in report.competitors:
        rows_for_brand = [dna_by_id[ad.id] for ad in competitor.ads if ad.id in dna_by_id]
        by_brand[competitor.name] = rows_for_brand
    return {
        "rows": rows,
        "user_score": user_total,
        "competitor_score": competitor_total,
        "gap": user_total - competitor_total,
        "dominant_signals": dominant_signals(by_brand),
        "has_comparison": bool(user_dna and competitor_dna),
    }
