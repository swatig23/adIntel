"""Unit tests for the BigQuery ads client.

These tests do NOT hit BigQuery. They exercise the schema-mapping logic
(`_row_to_ad_political`, `_row_to_ad_kaggle`, `_synthesise_body_text_political`)
with synthetic row dicts so we can verify the mapper is robust to real
column shapes before the user pays a single BQ query.

Live BQ smoke test is deferred until user's GCP project is set up
(see PLAN.md morning kickoff step 2).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import os

os.environ.setdefault("GOOGLE_API_KEY", "test-placeholder")

from adintel.clients import bq_ads
from adintel.models import CreativeType


def test_political_row_mapping_full_schema():
    """Realistic google_political_ads.creative_stats row -> Ad."""
    row = {
        "ad_id": "CR11223344",
        "ad_url": "https://adstransparency.google.com/advertiser/AR001/creative/CR11223344",
        "ad_type": "VIDEO",
        "regions": "US",
        "advertiser_id": "AR001",
        "advertiser_name": "Sierra Club",
        "date_range_start": date(2024, 1, 15),
        "date_range_end": date(2024, 3, 20),
        "num_of_days": 65,
        "impressions": "100000-1000000",
        "spend_range_min_usd": 50000,
        "spend_range_max_usd": 100000,
        "age_targeting": "25-54",
        "gender_targeting": "Any",
        "geo_targeting_included": "California, Oregon, Washington",
        "geo_targeting_excluded": None,
    }

    ad = bq_ads._row_to_ad_political(row)

    assert ad is not None
    assert ad.id == "CR11223344"
    assert ad.page_name == "Sierra Club"
    assert ad.creative_type == CreativeType.VIDEO
    assert "Sierra Club" in ad.body_text
    assert "$50,000" in ad.body_text and "$100,000" in ad.body_text
    assert "California" in ad.body_text
    assert ad.snapshot_url == row["ad_url"]
    assert ad.delivery_start.tzinfo is not None
    assert ad.delivery_stop is not None


def test_political_row_mapping_sparse_row():
    """Real BQ rows often have NULLs. Mapper must not blow up."""
    row = {
        "ad_id": "CR_sparse",
        "advertiser_name": "Small Org",
        "ad_type": None,
        "date_range_start": None,
        "date_range_end": None,
        "spend_range_min_usd": None,
        "spend_range_max_usd": None,
    }
    ad = bq_ads._row_to_ad_political(row)
    assert ad is not None
    assert ad.page_name == "Small Org"
    assert ad.creative_type == CreativeType.TEXT  # fallback for unknown ad_type
    assert ad.delivery_start.tzinfo is not None  # falls back to now(UTC)


def test_creative_type_mapper():
    assert bq_ads._cast_creative_type("VIDEO") == CreativeType.VIDEO
    assert bq_ads._cast_creative_type("IMAGE") == CreativeType.IMAGE
    assert bq_ads._cast_creative_type("Text") == CreativeType.TEXT
    assert bq_ads._cast_creative_type(None) == CreativeType.TEXT
    assert bq_ads._cast_creative_type("something-weird") == CreativeType.TEXT


def test_synthesised_body_text_carries_signal():
    """Downstream Gemini agent will pattern-match on this text; make sure
    the essentials survive."""
    row = {
        "advertiser_name": "League of Conservation Voters",
        "ad_type": "IMAGE",
        "date_range_start": date(2024, 6, 1),
        "date_range_end": date(2024, 8, 1),
        "spend_range_min_usd": 10000,
        "spend_range_max_usd": 50000,
        "impressions": "10000-100000",
        "age_targeting": "18-34",
        "gender_targeting": "Female",
        "geo_targeting_included": "Pennsylvania",
        "geo_targeting_excluded": "New York",
        "regions": "US",
    }
    body = bq_ads._synthesise_body_text_political(row)
    for needle in [
        "League of Conservation Voters",
        "IMAGE",
        "$10,000",
        "18-34",
        "Female",
        "Pennsylvania",
    ]:
        assert needle in body, f"body_text missing '{needle}': {body}"


def test_kaggle_row_mapping_with_typical_columns():
    row = {
        "id": "K001",
        "brand": "Nike",
        "body": "Just do it. New Air Max drops Friday.",
        "cta": "Shop Now",
        "start_date": date(2024, 5, 1),
        "end_date": date(2024, 6, 1),
        "ad_type": "image",
        "image_url": "https://example.com/nike.jpg",
    }
    ad = bq_ads._row_to_ad_kaggle(row)
    assert ad is not None
    assert ad.page_name == "Nike"
    assert "Air Max" in ad.body_text
    assert ad.creative_type == CreativeType.IMAGE
    assert ad.image_url == "https://example.com/nike.jpg"


def test_kaggle_row_mapping_falls_back_on_missing_columns():
    """If the Kaggle dataset uses unexpected column names the mapper
    must still produce SOMETHING rather than crashing."""
    row = {"random_column": "hello", "another": 42}
    ad = bq_ads._row_to_ad_kaggle(row)
    assert ad is not None
    assert ad.page_name == "Unknown"
    assert ad.body_text.startswith("Ad by Unknown")


def test_transcripts_row_mapping_real_schema():
    """Real schema, verified against the actual Kaggle file:
    Category, Advertiser, Product_or_spot, Ad_copy (capitalized)."""
    row = {
        "Category": "Automotive",
        "Advertiser": "BMW",
        "Product_or_spot": "BMW 3 Series",
        "Ad_copy": "The ultimate driving machine. Experience the all-new BMW 3 Series.",
    }
    ad = bq_ads._row_to_ad_transcripts(row)
    assert ad is not None
    assert ad.page_name == "BMW"
    assert "ultimate driving machine" in ad.body_text
    assert ad.link_caption == "BMW 3 Series"
    assert ad.delivery_stop is None  # no date data in this dataset


def test_transcripts_row_mapping_missing_advertiser():
    """Must not crash if Advertiser is blank -- falls back to 'Unknown'."""
    row = {"Category": "Retail", "Advertiser": None, "Ad_copy": "Big sale this weekend!"}
    ad = bq_ads._row_to_ad_transcripts(row)
    assert ad is not None
    assert ad.page_name == "Unknown"
    assert "Big sale" in ad.body_text
