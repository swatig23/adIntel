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
    GapItem,
    Pattern,
)
from adintel.report_dashboard import (
    competitor_chart_data,
    data_quality_summary,
    extract_headline,
    gap_coverage_chart_data,
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
    pattern1 = Pattern(category="hook", description="d1", frequency_pct=42.0)
    pattern2 = Pattern(category="copy_length", description="d2", frequency_pct=12.0)
    gap1 = GapItem(pattern=pattern1, user_has=False, recommendation="r1", priority=1)
    gap2 = GapItem(pattern=pattern2, user_has=True, recommendation="r2", priority=2)
    req = AnalysisRequest(user_brand="Acme", competitors=["BMW", "Audi"])
    return AnalysisReport(
        request=req,
        competitors=[comp1, comp2],
        patterns=[pattern1, pattern2],
        gaps=[gap1, gap2],
        executive_summary=(
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
