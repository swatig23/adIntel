"""GapAgent — compares the user's ads against winning patterns and produces
a prioritized list of deltas they should act on.
"""

from __future__ import annotations

import json
import re

from loguru import logger

from ..clients.gemini import generate_text
from ..models import Ad, GapItem, Pattern

SYSTEM_PROMPT = """You are a pragmatic performance-marketing consultant. Given
a user's ads and the winning patterns of their competitors, you identify the
SPECIFIC gaps the user should close first, in priority order.

Priority 1 = highest impact per effort. Be honest, not flattering.
"""

PROMPT_TEMPLATE = """You have two inputs.

WINNING PATTERNS (extracted from competitors' proven-winner ads):
{patterns_block}

USER'S ADS (currently running or paused):
{user_ads_block}

For EACH winning pattern, decide:
- Does the user's current ad set already use this pattern?
- What specific recommendation would you make?
- Priority 1-5 (1 = do this first, biggest lift).
- Cite 1-3 supporting ad IDs from that pattern's ``Evidence IDs``. Do not
  invent IDs and do not cite ads from another pattern.

Output STRICT JSON:
[
  {{
    "pattern_category": "<matches one of the pattern categories above>",
    "pattern_description": "<verbatim description>",
    "user_has": true|false,
    "recommendation": "one specific, actionable sentence",
    "priority": 1-5,
    "evidence_ad_ids": ["ad_id_1", "ad_id_2"],
    "evidence_summary": "One plain-English sentence explaining what these ads demonstrate."
  }}
]

Return ONLY the JSON array. No markdown fence. No prose.
"""


class GapAgent:
    async def run(self, user_ads: list[Ad], patterns: list[Pattern]) -> list[GapItem]:
        if not patterns:
            logger.warning("[GapAgent] no patterns; nothing to compare")
            return []

        patterns_block = "\n".join(
            f"- [{p.category}] {p.description} (freq: {p.frequency_pct:.0f}%; "
            f"Evidence IDs: {', '.join(p.evidence_ad_ids) or 'none available'})"
            for p in patterns
        )
        user_ads_block = self._format_user_ads(user_ads)

        prompt = PROMPT_TEMPLATE.format(
            patterns_block=patterns_block,
            user_ads_block=user_ads_block,
        )

        logger.info(
            f"[GapAgent] comparing {len(user_ads)} user ads against {len(patterns)} patterns"
        )
        raw = await generate_text(prompt, system=SYSTEM_PROMPT)
        return self._parse(raw, patterns)

    @staticmethod
    def _format_user_ads(ads: list[Ad]) -> str:
        if not ads:
            return "(The user has not run any ads yet — treat every winning pattern as a gap.)"
        return "\n".join(
            f"- [{a.creative_type.value}] CTA={a.cta or '?'}: {a.body_text[:200]}"
            for a in ads
        )

    @staticmethod
    def _parse(raw: str, patterns: list[Pattern]) -> list[GapItem]:
        by_desc = {p.description: p for p in patterns}
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        try:
            rows = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"[GapAgent] unparseable JSON: {e}\n{raw[:400]}")
            return []

        gaps: list[GapItem] = []
        for row in rows if isinstance(rows, list) else []:
            desc = row.get("pattern_description", "")
            matched = by_desc.get(desc) or next(
                (p for p in patterns if p.category == row.get("pattern_category")),
                None,
            )
            if not matched:
                continue
            evidence_ids = [
                ad_id
                for ad_id in row.get("evidence_ad_ids", [])
                if ad_id in matched.evidence_ad_ids
            ][:3] or matched.evidence_ad_ids[:3]
            user_has = bool(row.get("user_has", False))
            # The ranking is deterministic and intentionally simple: a
            # frequent competitor pattern with multiple cited examples is a
            # stronger opportunity, especially when the user lacks it.
            evidence_confidence = min(1.0, len(evidence_ids) / 3)
            opportunity_score = round(
                matched.frequency_pct * (1.0 if not user_has else 0.35) * (0.6 + 0.4 * evidence_confidence),
                1,
            )
            recommendation = row.get("recommendation", "").strip()
            gaps.append(
                GapItem(
                    pattern=matched,
                    user_has=user_has,
                    recommendation=recommendation,
                    priority=int(row.get("priority", 3)),
                    # A recommendation may only cite ads already attached to
                    # its matched pattern. Fall back to the pattern evidence
                    # when Gemini omits citations, so every useful gap has a
                    # verifiable trail whenever the pattern does.
                    evidence_ad_ids=evidence_ids,
                    evidence_summary=row.get("evidence_summary", "").strip(),
                    opportunity_score=opportunity_score,
                    action_variants=GapAgent._action_variants(matched, recommendation),
                )
            )
        gaps.sort(key=lambda g: (-g.opportunity_score, g.user_has, g.priority))
        logger.info(f"[GapAgent] produced {len(gaps)} gap items")
        return gaps

    @staticmethod
    def _action_variants(pattern: Pattern, recommendation: str) -> list[str]:
        """Produce useful, reviewable creative directions without another LLM call."""
        category = pattern.category.lower()
        if category == "hook":
            return [
                "Problem-led hook: name the customer's frustration in the first line.",
                "Question hook: turn the core customer pain point into a direct question.",
                "Proof-led hook: lead with a specific customer result or review.",
            ]
        if category in {"social_proof", "testimonial"}:
            return [
                "UGC concept: put a customer quote beside the product in use.",
                "Ratings concept: make a review score or short review the visual focal point.",
                "Results concept: lead with a measurable customer outcome, then explain why.",
            ]
        if category in {"offer", "cta"}:
            return [
                "Offer-first concept: place the concrete value proposition in the opening frame.",
                "Benefit-first concept: show the payoff before introducing the offer.",
                "Urgency concept: pair the offer with a truthful, specific reason to act now.",
            ]
        return [
            f"Direct execution: {recommendation}",
            f"Customer-led execution: demonstrate {pattern.description.lower()}",
            "Minimal execution: express the same idea with one focal visual and one clear CTA.",
        ]
