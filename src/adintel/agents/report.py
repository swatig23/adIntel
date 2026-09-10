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
1. **Strategy Name** (a punchy, memorable 2-5 word name for the recommended
   strategy, styled like a named marketing playbook -- e.g. "The Bold Proof
   Play" or "The Social Trust Sprint". Must be grounded in the actual
   top pattern below, not generic.)
2. **Headline** (one sentence -- the single most important insight)
3. **What's working for competitors** (2-3 sentences)
4. **Your top 3 moves this week** (numbered list; each starts with an action verb)
5. **What NOT to do** (one sentence based on the analysis)

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

        # No ads at all means nothing downstream had real data to work
        # with -- Analyze/Gap/Create already skip cheaply in this case
        # (see their own "no winning ads"/"no patterns" guards). Burning
        # a Gemini call here to summarize an empty analysis wastes quota
        # on output that's useless anyway, so we short-circuit instead.
        if total_ads == 0:
            logger.warning(
                f"[ReportAgent] skipping Gemini call for {brand} -- 0 ads "
                "ingested for any competitor, nothing to summarize"
            )
            names = ", ".join(c.name for c in competitors) or "the requested brands"
            return (
                "**Strategy Name**\nNo Data, No Strategy\n\n"
                "**Headline**\n"
                f"No ads were found for {names} in the current data source.\n\n"
                "**What's working for competitors**\n"
                "We couldn't analyze this -- none of the requested brands had any "
                "ads in the dataset.\n\n"
                "**Your top 3 moves this week**\n"
                "1. Double-check the brand names are spelled correctly.\n"
                "2. Try a different, more widely-known brand.\n"
                "3. Ask the team which brands the current data source covers.\n\n"
                "**What NOT to do**\n"
                "Don't treat this as a real competitive analysis -- there's no "
                "underlying data behind it."
            )

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
