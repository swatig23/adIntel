"""Tests for report_dashboard -- chart-data derivation and headline
extraction used by the dashboard-style report UI.
"""

from datetime import datetime, timezone

from adintel.models import (
    Ad,
    AnalysisReport,
    AnalysisRequest,
    Competitor,
    CreativeType,
    CreativeDNA,
    GapItem,
    Pattern,
)
from adintel.report_dashboard import (
    competitor_chart_data,
    competitive_scorecard,
    data_quality_summary,
    extract_headline,
    extract_strategy_name,
    gap_coverage_chart_data,
    gap_evidence_cards,
    pattern_chart_data,
)


def _make_ad(ad_id: str, page_name: str) -> Ad:
    return Ad(
        id=ad_id,
        page_id=f"p_{ad_id}",
        page_name=page_name,
        body_text="x",
        creative_type=CreativeType.TEXT,
        delivery_start=datetime.now(timezone.utc),
    )


def _make_report() -> AnalysisReport:
    ad1, ad2, ad3 = _make_ad("a1", "BMW"), _make_ad("a2", "BMW"), _make_ad("a3", "Audi")
    comp1 = Competitor(name="BMW", ads=[ad1, ad2])
    comp2 = Competitor(name="Audi", ads=[ad3])
    pattern1 = Pattern(category="hook", description="d1", frequency_pct=42.0, evidence_ad_ids=["a1", "missing"])
    pattern2 = Pattern(category="copy_length", description="d2", frequency_pct=12.0)
    gap1 = GapItem(
        pattern=pattern1,
        user_has=False,
        recommendation="r1",
        priority=1,
        evidence_ad_ids=["a1", "missing"],
        evidence_summary="BMW uses this opening repeatedly.",
    )
    gap2 = GapItem(pattern=pattern2, user_has=True, recommendation="r2", priority=2)
    req = AnalysisRequest(user_brand="Acme", competitors=["BMW", "Audi"])
    return AnalysisReport(
        request=req,
        competitors=[comp1, comp2],
        user_ads=[_make_ad("user-1", "Acme")],
        creative_dna=[
            CreativeDNA(ad_id="user-1", hook_type="benefit", creative_format="text", cta_strength=5, hook_strength=6, offer_clarity=3, visual_quality=5),
            CreativeDNA(ad_id="a1", hook_type="question", creative_format="text", has_social_proof=True, cta_strength=8, hook_strength=8, offer_clarity=8, visual_quality=5),
            CreativeDNA(ad_id="a2", hook_type="question", creative_format="text", has_social_proof=True, cta_strength=8, hook_strength=8, offer_clarity=8, visual_quality=5),
            CreativeDNA(ad_id="a3", hook_type="question", creative_format="text", has_social_proof=True, cta_strength=8, hook_strength=8, offer_clarity=8, visual_quality=5),
        ],
        patterns=[pattern1, pattern2],
        gaps=[gap1, gap2],
        executive_summary=(
            "**Strategy Name**\nThe Bold Contrast Play\n\n"
            "**Headline**\nBold contrast messaging is your biggest lever.\n\n"
            "**What's working**\nCompetitors lean aspirational."
        ),
        winner_ad_ids=["a1", "a3"],
    )


def test_extract_headline_pulls_the_headline_section():
    report = _make_report()
    assert extract_headline(report.executive_summary) == "Bold contrast messaging is your biggest lever."


def test_extract_headline_falls_back_to_first_line_on_unexpected_format():
    assert extract_headline("Just a plain sentence with no markdown.") == "Just a plain sentence with no markdown."


def test_extract_headline_handles_empty_string():
    assert extract_headline("") == ""


def test_extract_strategy_name_pulls_the_strategy_name_section():
    report = _make_report()
    assert extract_strategy_name(report.executive_summary) == "The Bold Contrast Play"


def test_extract_strategy_name_returns_empty_when_section_missing():
    # Unlike extract_headline, no first-line fallback -- a random sentence
    # mistaken for a strategy name would look worse than showing nothing.
    assert extract_strategy_name("**Headline**\nJust a headline, no strategy name.") == ""


def test_extract_strategy_name_handles_empty_string():
    assert extract_strategy_name("") == ""


def test_pattern_chart_data_formats_category_labels():
    report = _make_report()
    data = pattern_chart_data(report)
    assert data["labels"] == ["Hook", "Copy Length"]
    assert data["data"] == [42.0, 12.0]


def test_gap_coverage_chart_data_counts_has_vs_missing():
    report = _make_report()
    data = gap_coverage_chart_data(report)
    assert data["labels"] == ["Already Doing", "Gap Detected"]
    assert data["data"] == [1, 1]


def test_competitor_chart_data_uses_real_winner_ids_not_stale_property():
    report = _make_report()
    data = competitor_chart_data(report)
    assert data["labels"] == ["BMW", "Audi"]
    assert data["ads"] == [2, 1]
    # BMW has 2 ads but only a1 is a winner; Audi has 1 ad, a3 is a winner.
    assert data["winners"] == [1, 1]


def test_data_quality_summary_reports_no_gaps_when_all_brands_have_ads():
    report = _make_report()
    dq = data_quality_summary(report)
    assert dq["zero_ad_brands"] == []
    assert dq["total_ads"] == 3
    assert dq["is_empty"] is False
    assert dq["is_partial"] is False


def test_data_quality_summary_flags_brand_with_zero_ads():
    report = _make_report()
    report.competitors.append(Competitor(name="Tarzan", ads=[]))
    dq = data_quality_summary(report)
    assert dq["zero_ad_brands"] == ["Tarzan"]
    assert dq["is_partial"] is True
    assert dq["is_empty"] is False


def test_data_quality_summary_flags_fully_empty_report():
    req = AnalysisRequest(user_brand="Acme", competitors=["Tarzan"])
    empty_report = AnalysisReport(
        request=req,
        competitors=[Competitor(name="Tarzan", ads=[])],
        patterns=[],
        gaps=[],
        executive_summary="",
        winner_ad_ids=[],
    )
    dq = data_quality_summary(empty_report)
    assert dq["is_empty"] is True
    assert dq["zero_ad_brands"] == ["Tarzan"]


def test_gap_evidence_cards_resolves_only_real_ad_ids():
    cards = gap_evidence_cards(_make_report())
    evidence = cards["d1"]
    assert len(evidence) == 1
    assert evidence[0]["id"] == "a1"
    assert evidence[0]["brand"] == "BMW"


def test_competitive_scorecard_compares_user_and_winner_creative_dna():
    scorecard = competitive_scorecard(_make_report())
    assert scorecard["has_comparison"] is True
    assert scorecard["competitor_score"] > scorecard["user_score"]
    social_proof = next(row for row in scorecard["rows"] if row["dimension"] == "Social proof")
    assert social_proof["gap"] == -10.0
