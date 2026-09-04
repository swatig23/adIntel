"""Standalone BigQuery connectivity + schema smoke test.

Run this BEFORE flipping DATA_SOURCE=bq_political in .env. It catches
three separate failure modes that would otherwise surface as a confusing
error mid-demo:

1. Auth not set up (gcloud application-default credentials missing)
2. GCP_PROJECT_ID not set or invalid
3. The live table schema doesn't match what clients/bq_ads.py expects
   (the code was written from documentation, never verified live -- see
   the TODO comments in bq_ads.py)

Usage:
    cd adintel
    .venv/bin/python scripts/test_bigquery_connection.py

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
    print(f"      GCP_PROJECT_ID: {settings.gcp_project_id}")
    print(f"      BQ_POLITICAL_TABLE: {settings.bq_political_table}")
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
        print(f"      FAILED: {type(e).__name__}: {e}")
        print("      Common fix: run `gcloud auth application-default login`")
        return None


def check_schema(client) -> bool:
    print("\n[3/4] Verifying live table schema matches what bq_ads.py expects...")
    settings = get_settings()
    table = settings.bq_political_table  # project.dataset.table
    try:
        parts = table.split(".")
        if len(parts) != 3:
            print(f"      FAILED: BQ_POLITICAL_TABLE '{table}' is not project.dataset.table format")
            return False
        project, dataset, table_name = parts
        sql = f"""
            SELECT column_name
            FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMNS`
            WHERE table_name = @table_name
        """
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
            print(f"      FAILED: no columns found for table '{table}' - does it exist?")
            return False

        expected = set(_POLITICAL_COLUMNS)
        missing = expected - live_columns
        extra_available = live_columns - expected

        print(f"      Live table has {len(live_columns)} columns.")
        if missing:
            print(f"      MISMATCH: code expects these columns but they're NOT in the live table:")
            for col in sorted(missing):
                print(f"        - {col}")
            print("      Fix: update _POLITICAL_COLUMNS and the row-mapper in")
            print("      src/adintel/clients/bq_ads.py to match the live schema above.")
            return False

        print("      OK - all expected columns exist in the live table")
        if extra_available:
            sample = ", ".join(sorted(extra_available)[:5])
            print(f"      (bonus: {len(extra_available)} more columns available, unused: {sample}...)")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"      FAILED: {type(e).__name__}: {e}")
        return False


def check_real_query(client) -> bool:
    print("\n[4/4] Running a real sample query (advertiser search)...")
    try:
        from adintel.clients.bq_ads import fetch_political_ads_for_advertiser
        import asyncio

        # "Sierra Club" reliably returns rows in this public political ads dataset
        ads = asyncio.run(fetch_political_ads_for_advertiser("Sierra Club", limit=3))
        print(f"      Got {len(ads)} ads for a sample advertiser search")
        if ads:
            sample = ads[0]
            print(f"      Sample ad: id={sample.id}, advertiser={sample.page_name}")
            print(f"      Sample body_text: {sample.body_text[:120]}...")
        if not ads:
            print("      WARNING: query succeeded but returned 0 ads - try a different advertiser name")
            return False
        print("      OK")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"      FAILED: {type(e).__name__}: {e}")
        return False


def main() -> int:
    print("=" * 60)
    print("AdIntel - BigQuery Connectivity + Schema Smoke Test")
    print("=" * 60)

    if not check_settings():
        return 1

    client = check_auth_and_connect()
    if client is None:
        return 1

    schema_ok = check_schema(client)
    query_ok = check_real_query(client) if schema_ok else False

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
