"""Tests that LLM-supplied recommendation citations cannot become fake evidence."""

from adintel.agents.gap import GapAgent
from adintel.models import Pattern


def test_gap_parser_keeps_only_ids_belonging_to_the_matched_pattern():
    pattern = Pattern(
        category="hook",
        description="Open with a direct question.",
        frequency_pct=70,
        evidence_ad_ids=["winner-1", "winner-2"],
    )
    raw = '''[
      {
        "pattern_category": "hook",
        "pattern_description": "Open with a direct question.",
        "user_has": false,
        "recommendation": "Test a direct question as the opening hook.",
        "priority": 1,
        "evidence_ad_ids": ["winner-2", "invented-id"],
        "evidence_summary": "The supporting ads open with a question."
      }
    ]'''

    gaps = GapAgent._parse(raw, [pattern])

    assert len(gaps) == 1
    assert gaps[0].evidence_ad_ids == ["winner-2"]
    assert gaps[0].evidence_summary == "The supporting ads open with a question."
    assert gaps[0].opportunity_score > 0
    assert len(gaps[0].action_variants) == 3


def test_gap_parser_falls_back_to_valid_pattern_evidence_when_citations_missing():
    pattern = Pattern(
        category="cta",
        description="Use a direct CTA.",
        frequency_pct=60,
        evidence_ad_ids=["winner-3"],
    )
    raw = '''[{"pattern_category": "cta", "pattern_description": "Use a direct CTA.",
      "user_has": false, "recommendation": "Use a direct CTA.", "priority": 2}]'''

    gaps = GapAgent._parse(raw, [pattern])

    assert gaps[0].evidence_ad_ids == ["winner-3"]
