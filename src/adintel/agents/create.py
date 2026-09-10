"""CreateAgent — generates fresh ad creatives that mimic the winning
patterns, using Gemini for copy + Nano Banana (Gemini 2.5 Flash Image) for imagery.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from loguru import logger

from ..clients.gemini import generate_text
from ..models import GapItem, GeneratedCreative, Pattern

COPY_SYSTEM = """You write direct-response ad copy that mimics proven winners
while sounding fresh. Every element ties back to at least one winning pattern.
"""

COPY_PROMPT = """Create {n} ad creative concepts for the brand "{brand}".
Category / industry: {industry}.

You MUST reflect these winning patterns extracted from competitor ads:
{patterns_block}

Prioritized creative gaps to address (make each concept explicitly solve one):
{gaps_block}

For each concept, output STRICT JSON with:
{{
  "concepts": [
    {{
      "hook": "one-line attention grabber (max 12 words)",
      "body_copy": "2-3 sentences that build desire and lead into the CTA",
      "cta": "one of: Shop Now / Learn More / Get Started / Sign Up / Try Free / Order Today",
      "image_prompt": "a vivid, specific description of the image to generate — mention subject, style, lighting, mood, framing. NO text overlay in the image.",
      "rationale": "one sentence: which winning pattern(s) this leverages"
    }}
  ]
}}

Return ONLY the JSON object. No markdown fence.
"""


class CreateAgent:
    def __init__(self, output_dir: Path, n_creatives: int = 3):
        self.output_dir = output_dir
        self.n_creatives = n_creatives

    async def run(
        self,
        brand: str,
        industry: str,
        patterns: list[Pattern],
        gaps: list[GapItem] | None = None,
    ) -> list[GeneratedCreative]:
        if not patterns:
            logger.warning("[CreateAgent] no patterns; skipping creative generation")
            return []

        concepts = await self._generate_concepts(brand, industry, patterns, gaps or [])
        if not concepts:
            return []

        # Text concepts only — images are generated on-demand via Vertex AI
        # when the user clicks "Generate AI Visual" on each card.
        creatives: list[GeneratedCreative] = []
        for concept in concepts:
            creatives.append(
                GeneratedCreative(
                    filename="",
                    file_path="",
                    hook=concept["hook"],
                    body_copy=concept["body_copy"],
                    cta=concept["cta"],
                    inspired_by=[g.pattern.description for g in (gaps or [])[:3]] or [p.description for p in patterns[:3]],
                    rationale=concept.get("rationale", ""),
                )
            )
        logger.info(f"[CreateAgent] produced {len(creatives)} text concepts (images on-demand)")
        return creatives

    async def _generate_concepts(
        self, brand: str, industry: str, patterns: list[Pattern], gaps: list[GapItem]
    ) -> list[dict]:
        patterns_block = "\n".join(f"- [{p.category}] {p.description}" for p in patterns)
        gaps_block = "\n".join(
            f"- Opportunity {g.opportunity_score:.0f}/100: {g.recommendation}"
            for g in gaps[:3]
            if not g.user_has
        ) or "(No specific gaps supplied; use the strongest winning patterns.)"
        prompt = COPY_PROMPT.format(
            n=self.n_creatives,
            brand=brand,
            industry=industry or "general consumer",
            patterns_block=patterns_block,
            gaps_block=gaps_block,
        )
        raw = await generate_text(prompt, system=COPY_SYSTEM)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        try:
            payload = json.loads(cleaned)
            return payload.get("concepts", [])[: self.n_creatives]
        except json.JSONDecodeError as e:
            logger.error(f"[CreateAgent] bad JSON: {e}\n{raw[:400]}")
            return []

    @staticmethod
    def _draw_fallback_card(brand: str, idx: int, concept: dict, output_path: Path) -> Path:
        from PIL import Image, ImageDraw, ImageFont

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (600, 600), color=(28, 26, 23))  # Deep charcoal background, on-brand with AdIntel's editorial palette
        draw = ImageDraw.Draw(img)

        # Warm, restrained accent bar -- all three cards share the same
        # burgundy family instead of unrelated bright blue/pink/green, so
        # they read as one product instead of three random templates.
        accents = [(122, 46, 46), (168, 118, 58), (95, 35, 35)]
        bar_color = accents[idx % len(accents)]
        draw.rectangle([0, 0, 600, 90], fill=bar_color)

        # Try a real TTF for legible text; fall back to PIL's bitmap font
        # if none is available on this system (still renders, just smaller).
        def _font(size: int):
            for candidate in (
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ):
                try:
                    return ImageFont.truetype(candidate, size)
                except OSError:
                    continue
            return ImageFont.load_default()

        font_brand = _font(28)
        font_hook = _font(22)
        font_body = _font(16)
        font_cta = _font(18)

        draw.text((30, 30), brand.upper(), font=font_brand, fill=(255, 255, 255))

        def _wrap(text: str, width_chars: int) -> list[str]:
            words = text.split()
            lines, current = [], ""
            for w in words:
                trial = f"{current} {w}".strip()
                if len(trial) > width_chars and current:
                    lines.append(current)
                    current = w
                else:
                    current = trial
            if current:
                lines.append(current)
            return lines

        y = 130
        for line in _wrap(concept.get("hook", ""), 28):
            draw.text((30, y), line, font=font_hook, fill=(255, 255, 255))
            y += 32

        y += 20
        for line in _wrap(concept.get("body_copy", ""), 42):
            draw.text((30, y), line, font=font_body, fill=(203, 213, 225))
            y += 24

        # CTA pill anchored near the bottom
        cta_text = concept.get("cta", "Learn More")
        draw.rounded_rectangle([30, 520, 260, 565], radius=8, fill=bar_color)
        draw.text((50, 533), cta_text, font=font_cta, fill=(255, 255, 255))

        draw.text(
            (30, 575),
            "Local fallback — not generated by Gemini",
            font=_font(11),
            fill=(100, 116, 139),
        )

        img.save(output_path, "PNG")
        return output_path
