"""Local, permissioned visual corpus for reliable product demos."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from ..config import get_settings
from ..models import Ad, CreativeType, Platform


def asset_directory() -> Path:
    return Path(get_settings().curated_visual_asset_dir).resolve()


def _parse_datetime(value: Any, fallback: datetime | None = None) -> datetime:
    if not value:
        return fallback or datetime.now(timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = datetime.fromisoformat(f"{text}T00:00:00")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _safe_local_image_url(image_path: str | None) -> str | None:
    if not image_path:
        return None
    root = asset_directory()
    candidate = (root / image_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        logger.warning("[curated_visual] ignoring unsafe image_path")
        return None
    return f"/demo-assets/{candidate.name}" if candidate.is_file() else None


def _row_to_ad(row: dict[str, Any]) -> Ad | None:
    try:
        platform_values = row.get("platforms") or [row.get("platform", "facebook")]
        platforms = []
        for value in platform_values:
            try:
                platforms.append(Platform(str(value).lower()))
            except ValueError:
                continue
        first_seen = _parse_datetime(row.get("first_seen"))
        active = str(row.get("status", "active")).lower() == "active"
        return Ad(
            id=str(row["ad_id"]),
            page_name=str(row["advertiser"]),
            page_id=str(row.get("advertiser_id") or row["advertiser"].lower().replace(" ", "_")),
            creative_type=CreativeType(str(row.get("creative_type", "image")).lower()),
            body_text=str(row.get("body_text", "")),
            cta=row.get("cta"),
            link_caption=row.get("landing_url") or row.get("headline"),
            image_url=_safe_local_image_url(row.get("image_path")) or row.get("image_url"),
            platforms=platforms,
            delivery_start=first_seen,
            delivery_stop=None if active else _parse_datetime(row.get("last_seen"), first_seen),
            snapshot_url=row.get("snapshot_url"),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning(f"[curated_visual] skipping invalid record: {exc}")
        return None


async def fetch_curated_visual_ads(brand: str, limit: int = 25) -> list[Ad]:
    """Load records for an advertiser from the local visual-demo corpus."""
    path = Path(get_settings().curated_visual_file)
    if not path.is_file():
        logger.warning(f"[curated_visual] corpus not found: {path}")
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(f"[curated_visual] could not read corpus: {exc}")
        return []
    rows = payload.get("ads", []) if isinstance(payload, dict) else payload
    needle = brand.casefold().strip()
    ads = []
    for row in rows:
        if not isinstance(row, dict) or str(row.get("advertiser", "")).casefold().strip() != needle:
            continue
        ad = _row_to_ad(row)
        if ad:
            ads.append(ad)
    return ads[:limit]
