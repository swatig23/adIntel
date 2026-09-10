"""BigQuery ads client.

Queries a BigQuery table of ads and maps rows to our :class:`Ad` model.
Currently supports two shapes of table:

* ``bigquery-public-data.google_political_ads.creative_stats`` \u2014 Google's
  official political-ad transparency dataset. Real advertisers, real spend
  ranges, real impression ranges. Selected via ``DATA_SOURCE=bq_political``.

* A user-uploaded Kaggle dataset in the user's own project, selected via
  ``DATA_SOURCE=bq_kaggle`` + ``BQ_KAGGLE_TABLE=project.dataset.table``.
  The column-mapping function is deliberately tolerant of missing columns
  so a wide variety of ad-schema Kaggle datasets will Just Work.

Design notes / caveats:

1. The Google political-ads dataset does **not** include the ad's full
   creative text in ``creative_stats``. It has ``ad_url`` (link to
   Google's Ad Transparency Center) and rich metadata (spend, targeting,
   duration, ad_type). For pattern extraction we synthesise a
   descriptive body_text from the metadata so downstream agents still
   receive useful signal. TODO(user): to enrich with real ad copy, either
   scrape ad_url or join against another table you upload separately.

2. Auth uses Google Application Default Credentials. The user is
   expected to have run ``gcloud auth application-default login`` once
   after signing up for GCP. See PLAN.md morning kickoff step 2.

3. All queries are parameterised to prevent SQL injection even though
   inputs are advertiser names typed by a hackathon user, not untrusted
   web input.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from ..config import get_settings
from ..models import Ad, CreativeType, Platform

# TODO(user): if BQ schema differs, tweak this map. Column names below
# reflect the public google_political_ads.creative_stats schema as of
# 2025 documentation. Verify with:
#   SELECT column_name FROM `bigquery-public-data.google_political_ads.INFORMATION_SCHEMA.COLUMNS`
#   WHERE table_name = 'creative_stats';
_POLITICAL_COLUMNS = [
    "ad_id",
    "ad_url",
    "ad_type",
    "regions",
    "advertiser_id",
    "advertiser_name",
    "date_range_start",
    "date_range_end",
    "num_of_days",
    "impressions",
    "spend_range_min_usd",
    "spend_range_max_usd",
    "age_targeting",
    "gender_targeting",
    "geo_targeting_included",
    "geo_targeting_excluded",
]


def _get_client(project_id: str):
    """Lazy-load BigQuery client so import doesn't require the package
    unless BQ is actually used."""
    from google.cloud import bigquery  # imported lazily on purpose

    return bigquery.Client(project=project_id)


def _normalize_table_id(table: str) -> str:
    """Accept both legacy \"project:dataset.table\" (colon) and standard
    \"project.dataset.table\" (dot) formats -- BigQuery's console/docs
    commonly show the colon form, but Standard SQL backtick references
    require the dot form. Only the FIRST colon is replaced, since a
    project id itself never contains a colon."""
    return table.replace(":", ".", 1) if ":" in table else table


def _cast_creative_type(bq_ad_type: str | None) -> CreativeType:
    """Map BQ ad_type strings to our CreativeType enum."""
    if not bq_ad_type:
        return CreativeType.TEXT
    normalized = bq_ad_type.strip().upper()
    if "VIDEO" in normalized:
        return CreativeType.VIDEO
    if "IMAGE" in normalized:
        return CreativeType.IMAGE
    return CreativeType.TEXT


def _synthesise_body_text_political(row: dict[str, Any]) -> str:
    """Build a descriptive body_text from political-ad metadata.

    The Google political-ads BQ dataset does not include actual ad copy.
    We synthesise a rich descriptor so downstream Gemini pattern-mining
    still has signal to work with (behavioural + targeting patterns
    rather than copy patterns).
    """
    parts = [f"Political / social-issue ad by {row.get('advertiser_name', 'unknown advertiser')}."]

    ad_type = row.get("ad_type")
    if ad_type:
        parts.append(f"Format: {ad_type}.")

    start = row.get("date_range_start")
    end = row.get("date_range_end")
    if start and end:
        parts.append(f"Ran {start} to {end}.")

    spend_min = row.get("spend_range_min_usd")
    spend_max = row.get("spend_range_max_usd")
    if spend_min is not None and spend_max is not None:
        parts.append(f"Spend bracket: ${spend_min:,}\u2013${spend_max:,}.")

    impressions = row.get("impressions")
    if impressions:
        parts.append(f"Impressions bracket: {impressions}.")

    age = row.get("age_targeting")
    gender = row.get("gender_targeting")
    if age or gender:
        parts.append(f"Targeting: age={age or 'any'}, gender={gender or 'any'}.")

    geo_in = row.get("geo_targeting_included")
    geo_ex = row.get("geo_targeting_excluded")
    if geo_in or geo_ex:
        parts.append(f"Geo: included={geo_in or 'all'}, excluded={geo_ex or 'none'}.")

    regions = row.get("regions")
    if regions:
        parts.append(f"Regions served: {regions}.")

    return " ".join(parts)


def _row_to_ad_political(row: dict[str, Any]) -> Ad | None:
    """Convert one BQ row from google_political_ads.creative_stats to our Ad model."""
    try:
        ad_id = str(row.get("ad_id") or hashlib.md5(str(row).encode()).hexdigest()[:16])
        advertiser = row.get("advertiser_name") or "Unknown"

        start = row.get("date_range_start") or row.get("first_served_timestamp")
        end = row.get("date_range_end") or row.get("last_served_timestamp")

        # Normalise to timezone-aware datetimes.
        def _to_dt(v: Any) -> datetime | None:
            if v is None:
                return None
            if isinstance(v, datetime):
                return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
            # BQ returns date objects for DATE columns
            try:
                return datetime.combine(v, datetime.min.time(), tzinfo=timezone.utc)
            except Exception:  # noqa: BLE001
                return None

        start_dt = _to_dt(start) or datetime.now(timezone.utc)
        end_dt = _to_dt(end)

        return Ad(
            id=ad_id,
            page_name=advertiser,
            page_id=str(row.get("advertiser_id") or hashlib.md5(advertiser.encode()).hexdigest()[:12]),
            creative_type=_cast_creative_type(row.get("ad_type")),
            body_text=_synthesise_body_text_political(row),
            cta=None,  # not available in political ads dataset
            link_caption=None,
            image_url=None,  # TODO(user): scrape from ad_url if needed for vision
            platforms=[Platform.FACEBOOK],  # not accurate; Google-served, but keeps schema happy
            delivery_start=start_dt,
            delivery_stop=end_dt,
            snapshot_url=row.get("ad_url"),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[bq_ads] failed to map row: {e}")
        return None


def _row_to_ad_kaggle(row: dict[str, Any]) -> Ad | None:
    """Tolerant mapper for user-uploaded Kaggle ad datasets.

    Tries a bunch of common column-name variants. If your Kaggle dataset
    uses different names, either rename columns in BQ before querying or
    edit this function.

    TODO(user): once you upload a specific Kaggle CSV, tweak the column
    aliases below to match its schema. This function currently prefers
    columns like `ad_id`, `body`, `title`, `advertiser`, `spend`,
    `impressions`, `start_date`, `end_date`.
    """
    def _first(*keys, default=None):
        for k in keys:
            if k in row and row[k] not in (None, ""):
                return row[k]
        return default

    try:
        ad_id = str(_first("ad_id", "id", "campaign_id", default=hashlib.md5(str(row).encode()).hexdigest()[:16]))
        advertiser = _first("advertiser", "advertiser_name", "brand", "page_name", "company", default="Unknown")
        body = _first("body", "body_text", "ad_body", "text", "message", "description", default=f"Ad by {advertiser}")

        def _to_dt(v: Any) -> datetime:
            if v is None:
                return datetime.now(timezone.utc)
            if isinstance(v, datetime):
                return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
            try:
                return datetime.combine(v, datetime.min.time(), tzinfo=timezone.utc)
            except Exception:  # noqa: BLE001
                return datetime.now(timezone.utc)

        start = _to_dt(_first("start_date", "delivery_start", "first_served_timestamp"))
        end = _first("end_date", "delivery_stop", "last_served_timestamp")
        end_dt = _to_dt(end) if end else None

        return Ad(
            id=ad_id,
            page_name=str(advertiser),
            page_id=str(_first("page_id", "advertiser_id", default=hashlib.md5(str(advertiser).encode()).hexdigest()[:12])),
            creative_type=_cast_creative_type(_first("ad_type", "type", "creative_type", "format")),
            body_text=str(body)[:2000],
            cta=_first("cta", "call_to_action"),
            link_caption=_first("link_caption", "url", "landing_url"),
            image_url=_first("image_url", "creative_url", "media_url"),
            platforms=[Platform.FACEBOOK],
            delivery_start=start,
            delivery_stop=end_dt,
            snapshot_url=_first("snapshot_url", "ad_url"),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[bq_ads] kaggle row mapping failed: {e}")
        return None


def _row_to_ad_transcripts(row: dict[str, Any]) -> Ad | None:
    """Mapper for the Kaggle 'Advertisement Transcripts from Various
    Industries' dataset (kevinhartman0), uploaded to BQ as-is.

    Exact schema (capitalized, verified against the real file):
        Category, Advertiser, Product_or_spot, Ad_copy

    This dataset has NO date/duration columns -- it's a curated "one
    notable ad per brand" collection, not a time-series of running ads.
    Every ad gets delivery_start=now() and delivery_stop=None, which
    means LongevityAgent's default 90-day filter would silently drop
    every single ad. Callers using this source MUST set
    BQ_SKIP_LONGEVITY_FILTER=true (see config.py) so the pipeline treats
    every fetched ad as a winner instead of date-filtering them out.
    """
    try:
        advertiser = row.get("Advertiser") or "Unknown"
        ad_copy = row.get("Ad_copy") or f"Ad by {advertiser}"
        product = row.get("Product_or_spot") or ""

        ad_id = hashlib.md5(f"{advertiser}|{product}|{ad_copy}".encode()).hexdigest()[:16]

        return Ad(
            id=ad_id,
            page_name=str(advertiser),
            page_id=hashlib.md5(str(advertiser).encode()).hexdigest()[:12],
            creative_type=CreativeType.TEXT,  # transcripts are text-only, no image/video asset
            body_text=str(ad_copy)[:2000],
            cta=None,
            link_caption=str(product) if product else None,
            image_url=None,
            platforms=[Platform.FACEBOOK],
            delivery_start=datetime.now(timezone.utc),
            delivery_stop=None,
            snapshot_url=None,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[bq_ads] transcripts row mapping failed: {e}")
        return None


# \u2500\u2500\u2500 Public API \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500


async def fetch_political_ads_for_advertiser(advertiser_name: str, limit: int = 50) -> list[Ad]:
    """Query google_political_ads.creative_stats for one advertiser."""
    settings = get_settings()
    if not settings.gcp_project_id:
        raise RuntimeError(
            "GCP_PROJECT_ID not set. bq_political requires a GCP project for query billing "
            "(free-tier covers 1 TB/month). See PLAN.md morning kickoff step 2."
        )

    table = settings.bq_political_table
    columns = ", ".join(_POLITICAL_COLUMNS)
    # ILIKE-style match to allow partial advertiser typing ("Sierra" -> "Sierra Club")
    sql = f"""
        SELECT {columns}
        FROM `{table}`
        WHERE LOWER(advertiser_name) LIKE LOWER(@needle)
        ORDER BY date_range_end DESC NULLS LAST
        LIMIT @limit
    """

    def _run() -> list[dict[str, Any]]:
        from google.cloud import bigquery  # local import

        client = _get_client(settings.gcp_project_id)
        job = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("needle", "STRING", f"%{advertiser_name}%"),
                    bigquery.ScalarQueryParameter("limit", "INT64", limit),
                ]
            ),
        )
        return [dict(r) for r in job.result()]

    logger.info(f"[bq_ads:political] querying {table} for '{advertiser_name}' (limit {limit})")
    rows = await asyncio.to_thread(_run)
    ads = [ad for ad in (_row_to_ad_political(r) for r in rows) if ad is not None]
    logger.info(f"[bq_ads:political]   \u21b3 got {len(rows)} rows, mapped {len(ads)} ads")
    return ads


async def fetch_kaggle_ads_for_advertiser(advertiser_name: str, limit: int = 50) -> list[Ad]:
    """Query a user-owned BQ table (Kaggle upload) for one advertiser."""
    settings = get_settings()
    if not settings.gcp_project_id:
        raise RuntimeError("GCP_PROJECT_ID not set")
    if not settings.bq_kaggle_table:
        raise RuntimeError("BQ_KAGGLE_TABLE not set")

    table = _normalize_table_id(settings.bq_kaggle_table)

    # TODO(user): the WHERE-clause below assumes an `advertiser_name` column.
    # If your Kaggle dataset uses a different name (e.g. `brand`, `page_name`),
    # rename the column in BQ (`bq cp` + rename) or edit this query.
    sql = f"""
        SELECT *
        FROM `{table}`
        WHERE LOWER(advertiser_name) LIKE LOWER(@needle)
           OR LOWER(brand) LIKE LOWER(@needle)
           OR LOWER(page_name) LIKE LOWER(@needle)
        LIMIT @limit
    """

    def _run() -> list[dict[str, Any]]:
        from google.cloud import bigquery

        client = _get_client(settings.gcp_project_id)
        job = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("needle", "STRING", f"%{advertiser_name}%"),
                    bigquery.ScalarQueryParameter("limit", "INT64", limit),
                ]
            ),
        )
        return [dict(r) for r in job.result()]

    logger.info(f"[bq_ads:kaggle] querying {table} for '{advertiser_name}' (limit {limit})")
    rows = await asyncio.to_thread(_run)
    ads = [ad for ad in (_row_to_ad_kaggle(r) for r in rows) if ad is not None]
    logger.info(f"[bq_ads:kaggle]   \u21b3 got {len(rows)} rows, mapped {len(ads)} ads")
    return ads


async def fetch_transcripts_ads_for_advertiser(advertiser_name: str, limit: int = 50) -> list[Ad]:
    """Query the 'Advertisement Transcripts from Various Industries' BQ
    table (uploaded from kevinhartman0's Kaggle dataset) for one advertiser.

    Table schema is exact and known (unlike the generic bq_kaggle path):
        Category, Advertiser, Product_or_spot, Ad_copy

    Uses BQ_KAGGLE_TABLE for the table path -- same setting as bq_kaggle,
    since a user only ever has one Kaggle table uploaded at a time. Set
    DATA_SOURCE=bq_kaggle_transcripts to route here instead of the
    generic tolerant mapper.
    """
    settings = get_settings()
    if not settings.gcp_project_id:
        raise RuntimeError("GCP_PROJECT_ID not set")
    if not settings.bq_kaggle_table:
        raise RuntimeError("BQ_KAGGLE_TABLE not set")

    table = _normalize_table_id(settings.bq_kaggle_table)
    sql = f"""
        SELECT Category, Advertiser, Product_or_spot, Ad_copy
        FROM `{table}`
        WHERE LOWER(Advertiser) LIKE LOWER(@needle)
        LIMIT @limit
    """

    def _run() -> list[dict[str, Any]]:
        from google.cloud import bigquery

        client = _get_client(settings.gcp_project_id)
        job = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("needle", "STRING", f"%{advertiser_name}%"),
                    bigquery.ScalarQueryParameter("limit", "INT64", limit),
                ]
            ),
        )
        return [dict(r) for r in job.result()]

    logger.info(f"[bq_ads:transcripts] querying {table} for '{advertiser_name}' (limit {limit})")
    rows = await asyncio.to_thread(_run)
    ads = [ad for ad in (_row_to_ad_transcripts(r) for r in rows) if ad is not None]
    logger.info(f"[bq_ads:transcripts]   \u21b3 got {len(rows)} rows, mapped {len(ads)} ads")
    return ads
