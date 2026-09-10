"""Deterministic Creative DNA extraction and comparison helpers.

This deliberately uses observable creative signals only. It gives the product
an explainable base today; a future vision/ML classifier can replace or enrich
these heuristics without changing the report contract.
"""

from __future__ import annotations

import re
from collections import defaultdict

from .models import Ad, CreativeDNA


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE) for term in terms)


def extract_creative_dna(ads: list[Ad]) -> list[CreativeDNA]:
    """Create one transparent, repeatable feature record per ad."""
    result: list[CreativeDNA] = []
    for ad in ads:
        text = f"{ad.body_text} {ad.link_caption or ''}".lower()
        social_proof = _contains(text, ("review", "reviews", "rated", "testimonial", "customers", "trusted", "people love", "stars"))
        offer = bool(re.search(r"\b\d{1,2}%\b|\b(?:off|sale|discount|free shipping|save)\b", text))
        urgency = _contains(text, ("today", "now", "limited", "ends", "last chance", "hurry", "before it's gone"))
        demo = _contains(text, ("see how", "watch", "demo", "before and after", "results"))
        hook_type = (
            "question" if "?" in ad.body_text[:120]
            else "problem" if _contains(text, ("struggling", "tired", "stop", "without", "problem"))
            else "testimonial" if social_proof
            else "offer" if offer
            else "benefit"
        )
        strong_cta = _contains((ad.cta or "") + " " + text, ("shop now", "get started", "try free", "order today", "sign up", "learn more"))
        result.append(CreativeDNA(
            ad_id=ad.id,
            hook_type=hook_type,
            creative_format="product_demo" if demo else ad.creative_type.value,
            has_social_proof=social_proof,
            has_offer=offer,
            has_urgency=urgency,
            has_product_demo=demo,
            # A real vision classifier will make this signal richer. This
            # conservative proxy avoids claiming we detected a face from text.
            human_present=_contains(text, ("i ", "we ", "customer", "founder", "she ", "he ")),
            cta_strength=8 if strong_cta else (5 if ad.cta else 3),
            hook_strength=8 if hook_type in {"question", "problem", "testimonial"} else 6,
            offer_clarity=8 if offer else 3,
            visual_quality=7 if ad.image_url else (6 if ad.creative_type.value == "video" else 5),
        ))
    return result


def average_dimensions(dna: list[CreativeDNA]) -> dict[str, float]:
    """Return the six report dimensions on a 0-10 scale."""
    if not dna:
        return {name: 0.0 for name in DIMENSIONS}
    return {
        "Hook strength": round(sum(d.hook_strength for d in dna) / len(dna), 1),
        "Social proof": round(10 * sum(d.has_social_proof for d in dna) / len(dna), 1),
        "Offer clarity": round(sum(d.offer_clarity for d in dna) / len(dna), 1),
        "CTA": round(sum(d.cta_strength for d in dna) / len(dna), 1),
        "Product demo": round(10 * sum(d.has_product_demo for d in dna) / len(dna), 1),
        "Visual quality": round(sum(d.visual_quality for d in dna) / len(dna), 1),
    }


DIMENSIONS = ("Hook strength", "Social proof", "Offer clarity", "CTA", "Product demo", "Visual quality")


def dominant_signals(dna_by_brand: dict[str, list[CreativeDNA]]) -> list[str]:
    """Signals used by every competitor, ordered for the insight callout."""
    if not dna_by_brand:
        return []
    checks = {
        "social proof": lambda rows: all(d.has_social_proof for d in rows),
        "an offer": lambda rows: all(d.has_offer for d in rows),
        "product demonstrations": lambda rows: all(d.has_product_demo for d in rows),
        "question or problem-led hooks": lambda rows: all(d.hook_type in {"question", "problem"} for d in rows),
    }
    return [label for label, check in checks.items() if all(rows and check(rows) for rows in dna_by_brand.values())]
