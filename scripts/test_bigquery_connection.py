"""Standalone BigQuery connectivity + schema smoke test.

Run this BEFORE flipping DATA_SOURCE=bq_political in .env. It catches
failure modes that would otherwise surface as a confusing error mid-demo:

1. Auth not set up (gcloud application-default credentials missing)
2. GCP_PROJECT_ID not set or invalid
3. The live table schema doesn't match what clients/bq_ads.py expects
   (the code was written from documentation, never verified live -- see
   the TODO comments in bq_ads.py)
4. A real sample query, using an advertiser name auto-discovered from
   the live table (google_political_ads only contains political /
   social-issue advertisers, so a generic guess like "Google" reliably
   returns zero rows and looks like a bug when it isn't one)

Usage:
    cd adintel
    .venv/bin/python scripts/test_bigquery_connection.py
    .venv/bin/python scripts/test_bigquery_connection.py "Some Advertiser"

Exits 0 on success, 1 on failure, with a clear message either way.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from adintel.clients.bq_ads import _POLITICAL_COLUMNS  # noqa: E402
from adintel.config import get_settings  # noqa: E402


def check_settings() -> bool:
    print("[1/4] Checking configuration...")
    settings = get_settings()
    if not settings.gcp_project_id:
        print("      FAILED: GCP_PROJECT_ID is not set in .env")
        print("      Get a project ID from https://console.cloud.google.com/bigquery")
        return False
    print("      GCP_PROJECT_ID: " + settings.gcp_project_id)
    print("      BQ_POLITICAL_TABLE: " + settings.bq_political_table)
    print("      OK")
    return True


def check_auth_and_connect():
    print("\n[2/4] Testing BigQuery client auth...")
    try:
        from google.cloud import bigquery

        settings = get_settings()
        client = bigquery.Client(project=settings.gcp_project_id)
        # Trivial query that costs ~0 bytes -- just proves auth + connectivity
        job = client.query("SELECT 1 AS ok")
        rows = list(job.result())
        assert rows[0]["ok"] == 1
        print("      OK - authenticated and can run queries")
        return client
    except Exception as e:  # noqa: BLE001
        print("      FAILED: " + type(e).__name__ + ": " + str(e))
        print("      Common fix: run `gcloud auth application-default login`")
        return None


def check_schema(client) -> bool:
    print("\n[3/4] Verifying live table schema matches what bq_ads.py expects...")
    settings = get_settings()
    table = settings.bq_political_table  # project.dataset.table
    try:
        parts = table.split(".")
        if len(parts) != 3:
            print("      FAILED: BQ_POLITICAL_TABLE '" + table + "' is not project.dataset.table format")
            return False
        project, dataset, table_name = parts
        sql = (
            "SELECT column_name FROM `" + project + "." + dataset + ".INFORMATION_SCHEMA.COLUMNS` "
            "WHERE table_name = @table_name"
        )
        from google.cloud import bigquery

        job = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("table_name", "STRING", table_name),
                ]
            ),
        )
        live_columns = {row["column_name"] for row in job.result()}
        if not live_columns:
            print("      FAILED: no columns found for table '" + table + "' - does it exist?")
            return False

        expected = set(_POLITICAL_COLUMNS)
        missing = expected - live_columns
        extra_available = live_columns - expected

        print("      Live table has " + str(len(live_columns)) + " columns.")
        if missing:
            print("      MISMATCH: code expects these columns but they're NOT in the live table:")
            for col in sorted(missing):
                print("        - " + col)
            print("      Fix: update _POLITICAL_COLUMNS and the row-mapper in")
            print("      src/adintel/clients/bq_ads.py to match the live schema above.")
            return False

        print("      OK - all expected columns exist in the live table")
        if extra_available:
            sample = ", ".join(sorted(extra_available)[:5])
            print("      (bonus: " + str(len(extra_available)) + " more columns available, unused: " + sample + "...)")
        return True
    except Exception as e:  # noqa: BLE001
        print("      FAILED: " + type(e).__name__ + ": " + str(e))
        return False


def discover_real_advertiser(client, table: str) -> str | None:
    """Pull one real advertiser_name straight from the live table instead
    of guessing. google_political_ads only contains political/social-issue
    advertisers -- generic brand-name guesses (e.g. "Google") reliably
    return zero rows and look like a bug when they're not one."""
    try:
        sql = (
            "SELECT advertiser_name, COUNT(*) AS n FROM `" + table + "` "
            "WHERE advertiser_name IS NOT NULL "
            "GROUP BY advertiser_name ORDER BY n DESC LIMIT 1"
        )
        job = client.query(sql)
        rows = list(job.result())
        return rows[0]["advertiser_name"] if rows else None
    except Exception as e:  # noqa: BLE001
        print("      (could not auto-discover an advertiser: " + str(e) + ")")
        return None


def check_real_query(client, advertiser_override: str | None = None) -> bool:
    print("\n[4/4] Running a real sample query (advertiser search)...")
    try:
        from adintel.clients.bq_ads import fetch_political_ads_for_advertiser
        import asyncio

        settings = get_settings()
        advertiser = advertiser_override
        if not advertiser:
            print(
                "      Discovering a real advertiser name from the live table "
                "(this dataset only has political/social-issue advertisers, "
                "so generic brand-name guesses like 'Google' return 0 rows)..."
            )
            advertiser = discover_real_advertiser(client, settings.bq_political_table)
            if not advertiser:
                print("      FAILED: could not find any advertiser in the table")
                return False
            print("      Using discovered advertiser: '" + advertiser + "'")

        ads = asyncio.run(fetch_political_ads_for_advertiser(advertiser, limit=3))
        print("      Got " + str(len(ads)) + " ads for '" + advertiser + "'")
        if ads:
            sample = ads[0]
            print("      Sample ad: id=" + sample.id + ", advertiser=" + sample.page_name)
            print("      Sample body_text: " + sample.body_text[:120] + "...")
        if not ads:
            print("      WARNING: 0 ads for '" + advertiser + "' - try passing a name explicitly:")
            print('      .venv/bin/python scripts/test_bigquery_connection.py "Some Advertiser"')
            return False
        print("      OK")
        return True
    except Exception as e:  # noqa: BLE001
        print("      FAILED: " + type(e).__name__ + ": " + str(e))
        return False


def main() -> int:
    print("=" * 60)
    print("AdIntel - BigQuery Connectivity + Schema Smoke Test")
    print("=" * 60)

    advertiser_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if not check_settings():
        return 1

    client = check_auth_and_connect()
    if client is None:
        return 1

    schema_ok = check_schema(client)
    query_ok = check_real_query(client, advertiser_arg) if schema_ok else False

    print("\n" + "=" * 60)
    if schema_ok and query_ok:
        print("ALL CHECKS PASSED. Safe to set DATA_SOURCE=bq_political in .env")
        print("and restart the app.")
        return 0
    else:
        print("SOME CHECKS FAILED. Do not flip DATA_SOURCE=bq_political yet --")
        print("fix the issue above first, or stay on DATA_SOURCE=meta_stub")
        print("for your demo in the meantime.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
