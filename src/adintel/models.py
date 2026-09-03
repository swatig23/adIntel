"""Pydantic data models — the shared vocabulary between agents."""

from __future__ import annotations

from datetime import datetime, timezone


def _utcnow() -> datetime:
    """Timezone-aware UTC now (naive utcnow() is deprecated)."""
    return datetime.now(timezone.utc)
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Platform(str, Enum):
    """Meta Ad Library publisher platforms."""

    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    MESSENGER = "messenger"
    AUDIENCE_NETWORK = "audience_network"


class CreativeType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    TEXT = "text"


class Ad(BaseModel):
    """A single ad pulled from Meta Ad Library."""

    id: str
    page_name: str
    page_id: str
    creative_type: CreativeType
    body_text: str
    cta: Optional[str] = None
    link_caption: Optional[str] = None
    image_url: Optional[str] = None
    image_bytes: Optional[bytes] = Field(default=None, exclude=True)
    video_url: Optional[str] = None
    platforms: list[Platform] = Field(default_factory=list)
    delivery_start: datetime
    delivery_stop: Optional[datetime] = None
    snapshot_url: Optional[str] = None

    @property
    def days_running(self) -> int:
        end = self.delivery_stop or _utcnow()
        # Normalise to aware if the incoming datetime is naive
        start = self.delivery_start
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return max(0, (end - start).days)

    @property
    def is_winner(self) -> bool:
        """A 'proven winner' has been running long enough that Meta's
        auction economics suggest it's profitable for the advertiser."""
        return self.days_running >= 90 and self.delivery_stop is None


class Competitor(BaseModel):
    """A brand we analyze."""

    name: str
    page_id: Optional[str] = None
    ads: list[Ad] = Field(default_factory=list)

    @property
    def winner_ads(self) -> list[Ad]:
        return [a for a in self.ads if a.is_winner]


class Pattern(BaseModel):
    """A recurring pattern extracted across winning ads."""

    category: str  # e.g. "hook", "visual", "cta", "offer", "copy_length"
    description: str
    frequency_pct: float
    evidence_ad_ids: list[str] = Field(default_factory=list)


class GapItem(BaseModel):
    """A specific delta between the user's ads and winning patterns."""

    pattern: Pattern
    user_has: bool
    recommendation: str
    priority: int  # 1 = highest


class GeneratedCreative(BaseModel):
    """An ad creative produced by the Create agent."""

    filename: str
    file_path: str
    hook: str
    body_copy: str
    cta: str
    inspired_by: list[str] = Field(default_factory=list)  # winning ad IDs
    rationale: str


class AnalysisRequest(BaseModel):
    """User input to /analyze."""

    user_brand: str
    competitors: list[str] = Field(min_length=1, max_length=10)
    industry_hint: Optional[str] = None
    generate_creatives: bool = True


class AnalysisReport(BaseModel):
    """Everything the pipeline produces, delivered to the UI."""

    request: AnalysisRequest
    competitors: list[Competitor]
    patterns: list[Pattern]
    gaps: list[GapItem]
    generated_creatives: list[GeneratedCreative] = Field(default_factory=list)
    executive_summary: str
    created_at: datetime = Field(default_factory=_utcnow)
