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

Output STRICT JSON:
[
  {{
    "pattern_category": "<matches one of the pattern categories above>",
    "pattern_description": "<verbatim description>",
    "user_has": true|false,
    "recommendation": "one specific, actionable sentence",
    "priority": 1-5
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
            f"- [{p.category}] {p.description} (freq: {p.frequency_pct:.0f}%)" for p in patterns
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
            gaps.append(
                GapItem(
                    pattern=matched,
                    user_has=bool(row.get("user_has", False)),
                    recommendation=row.get("recommendation", "").strip(),
                    priority=int(row.get("priority", 3)),
                )
            )
        gaps.sort(key=lambda g: (g.user_has, g.priority))
        logger.info(f"[GapAgent] produced {len(gaps)} gap items")
        return gaps
