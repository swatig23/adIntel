"""AnalyzeAgent — feeds all winning ads (copy + images) into Gemini in ONE shot
to extract cross-cutting patterns.

This is the long-context flex: 100+ ads' worth of copy + N images analyzed
together, so Gemini can see genuine cross-ad patterns humans would miss.
"""

from __future__ import annotations

import json
import re
from typing import Iterable

from loguru import logger

from ..clients.gemini import generate_from_multimodal, generate_text
from ..models import Ad, Pattern

SYSTEM_PROMPT = """You are a senior direct-response advertising strategist.
You study ad creatives and extract the *specific, teachable patterns* that
appear repeatedly among the best-performing ads.

Your patterns should be concrete and actionable. Bad: "uses emotion". Good:
"Opens with a rhetorical question addressing a specific pain point in the first 8 words".
"""

PROMPT_TEMPLATE = """You are looking at the winning ads from {n_brands} competitors
in the same category. These ads have all been running for 90+ days, meaning
Meta's auction has determined they are profitable.

Your job: find the {top_k} MOST IMPORTANT recurring patterns.

For each pattern, output STRICT JSON:
[
  {{
    "category": "hook|visual|cta|offer|copy_length|social_proof|tone",
    "description": "concrete, teachable description in one sentence",
    "frequency_pct": 0-100 estimate of how many winning ads use this pattern,
    "evidence_ad_ids": ["ad_id_1", "ad_id_2", "ad_id_3"]
  }}
]

Return ONLY the JSON array, no prose, no markdown fence.

Here are the winning ads (copy shown; images attached where available):

{ads_block}
"""


class AnalyzeAgent:
    def __init__(self, max_images: int = 3, top_k_patterns: int = 6):
        self.max_images = max_images
        self.top_k_patterns = top_k_patterns

    async def run(self, winning_ads: list[Ad]) -> list[Pattern]:
        if not winning_ads:
            logger.warning("[AnalyzeAgent] no winning ads to analyze")
            return []

        ads_block = self._format_ads(winning_ads)
        image_urls = [a.image_url for a in winning_ads if a.image_url][: self.max_images]

        prompt = PROMPT_TEMPLATE.format(
            n_brands=len({a.page_name for a in winning_ads}),
            top_k=self.top_k_patterns,
            ads_block=ads_block,
        )

        logger.info(
            f"[AnalyzeAgent] Gemini call — {len(winning_ads)} ads, {len(image_urls)} images"
        )

        if image_urls:
            try:
                raw = await generate_from_multimodal(prompt, image_urls, system=SYSTEM_PROMPT)
            except Exception as e:
                logger.warning(
                    f"[AnalyzeAgent] Multimodal call unavailable ({e}); falling back to text copy analysis"
                )
                raw = await generate_text(prompt, system=SYSTEM_PROMPT)
        else:
            raw = await generate_text(prompt, system=SYSTEM_PROMPT)

        return self._parse_patterns(raw, winning_ads)

    @staticmethod
    def _format_ads(ads: Iterable[Ad]) -> str:
        chunks = []
        for a in ads:
            chunks.append(
                f"---\n"
                f"AD_ID: {a.id}\n"
                f"BRAND: {a.page_name}\n"
                f"TYPE: {a.creative_type.value}\n"
                f"DAYS_RUNNING: {a.days_running}\n"
                f"CTA: {a.cta or '(none)'}\n"
                f"BODY:\n{a.body_text}\n"
            )
        return "\n".join(chunks)

    def _parse_patterns(self, raw: str, winning_ads: Iterable[Ad] | None = None) -> list[Pattern]:
        # Strip common markdown fences the model sometimes adds
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"[AnalyzeAgent] Gemini returned unparseable JSON: {e}\n{raw[:400]}")
            return []
        valid_ids = {ad.id for ad in winning_ads} if winning_ads is not None else None
        patterns: list[Pattern] = []
        for row in data if isinstance(data, list) else []:
            try:
                pattern = Pattern(**row)
                # Never let an LLM-invented ID become product evidence. This
                # also makes the report safe to persist and render later.
                if valid_ids is not None:
                    pattern.evidence_ad_ids = [
                        ad_id for ad_id in pattern.evidence_ad_ids if ad_id in valid_ids
                    ][:3]
                patterns.append(pattern)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[AnalyzeAgent] skipping malformed pattern: {e}")
        logger.info(f"[AnalyzeAgent] extracted {len(patterns)} patterns")
        return patterns
