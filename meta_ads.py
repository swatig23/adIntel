"""Meta Ad Library client.

Two modes:
* Live — hits https://graph.facebook.com/v18.0/ads_archive with an access token.
* Stub — returns deterministic realistic sample ads so the demo runs offline.

Toggle via ``USE_META_STUB`` env var.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from loguru import logger

from ..config import get_settings
from ..models import Ad, CreativeType, Platform

META_API_BASE = "https://graph.facebook.com/v18.0/ads_archive"


# ─── Stub data generator ────────────────────────────────────────────────

_HOOK_TEMPLATES = [
    "Tired of {pain}?",
    "The {adjective} way to {benefit}",
    "How I {achievement} in {timeframe}",
    "Stop {bad_habit}. Start {good_habit}.",
    "{number} reasons to switch to {brand}",
    "This changed everything for {audience}",
    "Meet the {product} that's breaking the internet",
    "You're one click away from {outcome}",
]

_CTA_OPTIONS = ["Shop Now", "Learn More", "Get Started", "Sign Up", "Try Free", "Order Today"]

_PLACEHOLDERS = {
    "pain": ["waiting", "guessing", "overpaying", "settling"],
    "adjective": ["smartest", "easiest", "fastest", "boldest"],
    "benefit": ["look sharp", "feel great", "save time", "spend less"],
    "achievement": ["cut my costs 40%", "doubled my sales", "quit my day job"],
    "timeframe": ["30 days", "one weekend", "under a week"],
    "bad_habit": ["overpaying", "wasting time", "second-guessing"],
    "good_habit": ["winning", "saving", "shipping"],
    "number": ["3", "5", "7", "10"],
    "audience": ["founders", "creators", "small teams", "busy parents"],
    "product": ["app", "platform", "tool", "system"],
    "outcome": ["freedom", "clarity", "results", "growth"],
}


def _seeded_random(key: str) -> random.Random:
    """Deterministic RNG so a given brand always yields the same fake ads."""
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:16], 16)
    return random.Random(seed)


def _generate_stub_ads(brand: str, count: int = 25) -> list[Ad]:
    rng = _seeded_random(brand)
    ads: list[Ad] = []
    for i in range(count):
        template = rng.choice(_HOOK_TEMPLATES)
        filled = template
        for placeholder, options in _PLACEHOLDERS.items():
            filled = filled.replace("{" + placeholder + "}", rng.choice(options))
        filled = filled.replace("{brand}", brand)

        body = (
            f"{filled}\n\n"
            f"Discover why thousands trust {brand}. "
            f"Free shipping on your first order. Limited time offer."
        )

        # Vary delivery windows so we get a natural mix of winners/losers
        days_ago_start = rng.randint(5, 240)
        still_running = rng.random() < 0.55
        start = datetime.now(timezone.utc) - timedelta(days=days_ago_start)
        stop = None if still_running else start + timedelta(days=rng.randint(3, 40))

        creative_type = rng.choices(
            [CreativeType.IMAGE, CreativeType.VIDEO, CreativeType.CAROUSEL],
            weights=[0.6, 0.3, 0.1],
        )[0]

        ads.append(
            Ad(
                id=f"stub_{brand.lower().replace(' ', '_')}_{i:03d}",
                page_name=brand,
                page_id=f"page_{hashlib.md5(brand.encode()).hexdigest()[:12]}",
                creative_type=creative_type,
                body_text=body,
                cta=rng.choice(_CTA_OPTIONS),
                link_caption=f"{brand.lower().replace(' ', '')}.com",
                image_url=f"https://picsum.photos/seed/{brand}{i}/600/600",
                platforms=[Platform.FACEBOOK, Platform.INSTAGRAM],
                delivery_start=start,
                delivery_stop=stop,
                snapshot_url=f"https://www.facebook.com/ads/library/?id=stub_{i}",
            )
        )
    return ads


# ─── Live client ────────────────────────────────────────────────────────


async def _fetch_live_ads(brand: str, limit: int = 25) -> list[Ad]:
    settings = get_settings()
    if not settings.meta_access_token:
        raise RuntimeError("META_ACCESS_TOKEN not set but USE_META_STUB=false")

    params = {
        "search_terms": brand,
        "ad_reached_countries": "['US']",
        "ad_active_status": "ALL",
        "limit": limit,
        "fields": ",".join(
            [
                "id",
                "page_id",
                "page_name",
                "ad_creative_bodies",
                "ad_creative_link_captions",
                "ad_creative_link_titles",
                "ad_delivery_start_time",
                "ad_delivery_stop_time",
                "ad_snapshot_url",
                "publisher_platforms",
            ]
        ),
        "access_token": settings.meta_access_token,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(META_API_BASE, params=params)
        r.raise_for_status()
        payload = r.json()

    ads: list[Ad] = []
    for row in payload.get("data", []):
        try:
            body = (row.get("ad_creative_bodies") or [""])[0]
            start_str = row.get("ad_delivery_start_time")
            stop_str = row.get("ad_delivery_stop_time")
            ads.append(
                Ad(
                    id=row["id"],
                    page_name=row.get("page_name", brand),
                    page_id=str(row.get("page_id", "")),
                    creative_type=CreativeType.IMAGE,  # Ad Library doesn't tell us reliably
                    body_text=body,
                    link_caption=(row.get("ad_creative_link_captions") or [None])[0],
                    delivery_start=datetime.fromisoformat(start_str.replace("Z", "+00:00")),
                    delivery_stop=(
                        datetime.fromisoformat(stop_str.replace("Z", "+00:00")) if stop_str else None
                    ),
                    snapshot_url=row.get("ad_snapshot_url"),
                    platforms=[Platform(p) for p in row.get("publisher_platforms", [])],
                )
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Skipping malformed ad row: {e}")
    return ads


# ─── Public API ─────────────────────────────────────────────────────────


async def fetch_ads_for_brand(brand: str, limit: int = 25) -> list[Ad]:
    """Return recent ads for a given brand, respecting stub/live toggle."""
    settings = get_settings()
    if settings.use_meta_stub:
        logger.info(f"[meta:stub] generating {limit} fake ads for '{brand}'")
        return _generate_stub_ads(brand, count=limit)
    logger.info(f"[meta:live] fetching ads for '{brand}'")
    return await _fetch_live_ads(brand, limit=limit)
