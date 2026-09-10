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


class CreativeDNA(BaseModel):
    """Explainable, normalized attributes extracted from one ad.

    These are intentionally creative signals, not performance scores. They
    let the dashboard compare the user's ads with competitors using a stable
    vocabulary, even when performance metrics are unavailable.
    """

    ad_id: str
    hook_type: str
    creative_format: str
    has_social_proof: bool = False
    has_offer: bool = False
    has_urgency: bool = False
    has_product_demo: bool = False
    human_present: bool = False
    cta_strength: int = Field(ge=1, le=10)
    hook_strength: int = Field(ge=1, le=10)
    offer_clarity: int = Field(ge=1, le=10)
    visual_quality: int = Field(ge=1, le=10)


class GapItem(BaseModel):
    """A specific delta between the user's ads and winning patterns."""

    pattern: Pattern
    user_has: bool
    recommendation: str
    priority: int  # 1 = highest
    # These IDs must point to ads that support ``pattern``. Keeping the
    # references on the recommendation makes a saved report self-explanatory
    # and lets the UI show the exact evidence behind each suggested action.
    evidence_ad_ids: list[str] = Field(default_factory=list)
    evidence_summary: str = ""
    # Deterministic 0-100 ranking based on prevalence, the observed user gap,
    # and strength of source evidence. Gemini writes the advice; it does not
    # get to invent this score.
    opportunity_score: float = Field(default=0, ge=0, le=100)
    action_variants: list[str] = Field(default_factory=list)


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
    user_ads: list[Ad] = Field(default_factory=list)
    creative_dna: list[CreativeDNA] = Field(default_factory=list)
    patterns: list[Pattern]
    gaps: list[GapItem]
    generated_creatives: list[GeneratedCreative] = Field(default_factory=list)
    executive_summary: str
    # The ACTUAL ad IDs LongevityAgent flagged as winners for this run --
    # NOT recomputed via Competitor.winner_ads (which hardcodes the 90-day
    # rule and ignores BQ_SKIP_LONGEVITY_FILTER). Sources without delivery
    # dates correctly show every ad here instead of always displaying 0.
    winner_ad_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)

    @property
    def winner_count(self) -> int:
        return len(self.winner_ad_ids)

    def winners_for(self, competitor: "Competitor") -> list[Ad]:
        """Ads for this competitor that were actually flagged as winners
        by LongevityAgent -- respects BQ_SKIP_LONGEVITY_FILTER, unlike
        Competitor.winner_ads."""
        winner_ids = set(self.winner_ad_ids)
        return [a for a in competitor.ads if a.id in winner_ids]
