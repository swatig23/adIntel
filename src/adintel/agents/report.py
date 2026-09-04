"""ReportAgent — writes the final executive summary.

Takes everything the pipeline produced and turns it into a crisp narrative
that a busy marketer can act on immediately.
"""

from __future__ import annotations

from loguru import logger

from ..clients.gemini import generate_text
from ..models import Competitor, GapItem, Pattern

SYSTEM = """You are a CMO-level writer. You turn analytical output into a
one-page executive summary that a busy founder can act on in 5 minutes.
Use plain English, short paragraphs, and lead with the single biggest lift.
Never invent facts not present in the inputs.
"""

PROMPT = """Write an executive summary for {brand}'s competitor ad analysis.

Competitors analyzed: {competitor_names}
Total ads examined: {total_ads}
Winning ads (running 90+ days): {winner_count}

Top winning patterns:
{patterns_block}

Priority gaps for {brand} to close:
{gaps_block}

Structure your response:
1. **Headline** (one sentence — the single most important insight)
2. **What's working for competitors** (2-3 sentences)
3. **Your top 3 moves this week** (numbered list; each starts with an action verb)
4. **What NOT to do** (one sentence based on the analysis)

Keep it under 220 words. No preamble. No sign-off.
"""


class ReportAgent:
    async def run(
        self,
        brand: str,
        competitors: list[Competitor],
        patterns: list[Pattern],
        gaps: list[GapItem],
        winner_count: int,
    ) -> str:
        total_ads = sum(len(c.ads) for c in competitors)
        winners = winner_count

        patterns_block = (
            "\n".join(
                f"- [{p.category}] {p.description} ({p.frequency_pct:.0f}% of winners)"
                for p in patterns
            )
            or "(none extracted)"
        )
        gaps_block = (
            "\n".join(
                f"- P{g.priority} — {g.recommendation}" for g in gaps[:5]
            )
            or "(no gaps identified)"
        )

        prompt = PROMPT.format(
            brand=brand,
            competitor_names=", ".join(c.name for c in competitors),
            total_ads=total_ads,
            winner_count=winners,
            patterns_block=patterns_block,
            gaps_block=gaps_block,
        )
        logger.info(f"[ReportAgent] writing summary for {brand}")
        return await generate_text(prompt, system=SYSTEM)
