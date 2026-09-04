"""CreateAgent — generates fresh ad creatives that mimic the winning
patterns, using Gemini for copy + Nano Banana (Gemini 2.5 Flash Image) for imagery.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from loguru import logger

from ..clients.gemini import generate_image, generate_text
from ..models import GeneratedCreative, Pattern

COPY_SYSTEM = """You write direct-response ad copy that mimics proven winners
while sounding fresh. Every element ties back to at least one winning pattern.
"""

COPY_PROMPT = """Create {n} ad creative concepts for the brand "{brand}".
Category / industry: {industry}.

You MUST reflect these winning patterns extracted from competitor ads:
{patterns_block}

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
    ) -> list[GeneratedCreative]:
        if not patterns:
            logger.warning("[CreateAgent] no patterns; skipping creative generation")
            return []

        concepts = await self._generate_concepts(brand, industry, patterns)
        if not concepts:
            return []

        # Generate images in parallel
        results = await asyncio.gather(
            *(self._render_image(brand, i, c) for i, c in enumerate(concepts)),
            return_exceptions=True,
        )

        creatives: list[GeneratedCreative] = []
        for concept, path_or_err in zip(concepts, results):
            if isinstance(path_or_err, Exception):
                logger.warning(f"[CreateAgent] image failed: {path_or_err}")
                continue
            path: Path = path_or_err
            creatives.append(
                GeneratedCreative(
                    filename=path.name,
                    file_path=str(path),
                    hook=concept["hook"],
                    body_copy=concept["body_copy"],
                    cta=concept["cta"],
                    inspired_by=[p.description for p in patterns[:3]],
                    rationale=concept.get("rationale", ""),
                )
            )
        logger.info(f"[CreateAgent] produced {len(creatives)} creatives")
        return creatives

    async def _generate_concepts(
        self, brand: str, industry: str, patterns: list[Pattern]
    ) -> list[dict]:
        patterns_block = "\n".join(f"- [{p.category}] {p.description}" for p in patterns)
        prompt = COPY_PROMPT.format(
            n=self.n_creatives,
            brand=brand,
            industry=industry or "general consumer",
            patterns_block=patterns_block,
        )
        raw = await generate_text(prompt, system=COPY_SYSTEM, json_mode=True)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        try:
            payload = json.loads(cleaned)
            return payload.get("concepts", [])[: self.n_creatives]
        except json.JSONDecodeError as e:
            logger.error(f"[CreateAgent] bad JSON: {e}\n{raw[:400]}")
            return []

    async def _render_image(self, brand: str, idx: int, concept: dict) -> Path:
        out = self.output_dir / f"{brand.lower().replace(' ', '_')}_creative_{idx + 1}.png"
        prompt = (
            f"Advertising image for {brand}. "
            f"{concept.get('image_prompt', '')} "
            f"Professional product photography, high resolution, "
            f"crisp lighting, brand-forward composition. No text or logos in the image."
        )
        try:
            return await generate_image(prompt, out, timeout=4.0)
        except Exception as e:
            logger.info(f"[CreateAgent] API image gen unavailable ({e}); creating styled concept graphic")
            return self._draw_fallback_card(brand, idx, concept, out)

    @staticmethod
    def _draw_fallback_card(brand: str, idx: int, concept: dict, output_path: Path) -> Path:
        from PIL import Image, ImageDraw

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (600, 600), color=(15, 23, 42))  # Dark slate background
        draw = ImageDraw.Draw(img)

        # Header accent bar
        colors = [(79, 70, 229), (236, 72, 153), (16, 185, 129)]
        bar_color = colors[idx % len(colors)]
        draw.rectangle([0, 0, 600, 100], fill=bar_color)

        # Draw card framing
        draw.rectangle([30, 130, 570, 480], outline=(51, 65, 85), width=2)
        draw.rectangle([50, 430, 220, 470], fill=bar_color)

        img.save(output_path, "PNG")
        return output_path
