# AdIntel - Build Status

**Snapshot:** 2026-09-03, 2:30 AM IST
**Deadline:** 8 PM IST today

Legend: `[x]` done & tested | `[~]` code written, needs live test | `[ ]` not started

---

## Phase A - Ship-safe MVP (locked scope for 8 PM)

### Foundation
- [x] `uv` project on Python 3.12 with Walmart artifactory index
- [x] All deps installed & lockfile stable
- [x] `.gitignore`, `.env.example`, `.python-version`
- [x] Directory structure: `src/adintel/{agents,clients,templates,static}`
- [x] Pydantic models: `Ad`, `Competitor`, `Pattern`, `GapItem`, `GeneratedCreative`, `AnalysisRequest`, `AnalysisReport`
- [x] `Settings` (pydantic-settings) reading from `.env`
- [x] Datetime deprecation warnings cleaned up (timezone-aware UTC)

### Data ingestion (IngestAgent)
- [x] `fetch_ads_for_brand()` with two backends
- [x] Stub mode: deterministic per-brand synthetic ads (25 per brand default)
- [x] Stub mode: realistic hook templates, CTAs, delivery windows
- [~] Live mode: Meta Ad Library v18 API - code written, needs Meta token (10 min ID verification, not weeks as earlier claimed)
- [ ] **BigQuery mode (new plan): query `bigquery-public-data.google_political_ads` - build overnight**
- [x] Smoke test: 3 tests green (fetch, deterministic, longevity filter)

### Data source dispatcher (NEW as of 2026-09-03)
- [x] `DATA_SOURCE` env var added with values: `meta_stub` | `bq_political` | `meta_live` | `bq_kaggle`
- [x] `clients/bq_ads.py` — queries `bigquery-public-data.google_political_ads.creative_stats`
- [x] Schema shim: BQ political-ads columns → our `Ad` Pydantic model (defensive, tolerates NULLs)
- [x] Kaggle-generic mapper: tolerant to different column-name conventions (advertiser/brand/page_name etc.)
- [x] `clients/ads.py` dispatcher module (routes on `DATA_SOURCE`)
- [x] `IngestAgent` now calls dispatcher, wraps failures in try/except so one bad brand doesn't kill the run
- [x] `google-cloud-bigquery` added to `pyproject.toml`
- [x] `/healthz` now reports `data_source`, `storage_backend`, and whether keys are set
- [x] 6 unit tests for BQ mappers using synthetic rows (no live BQ needed) — all green
- [ ] **TODO (morning kickoff step 3.5): run `uv sync` to install google-cloud-bigquery in venv**
- [ ] **TODO (morning kickoff step 6.5): after GCP setup, run one live BQ query smoke-check** (see PLAN.md)
- [ ] **TODO (post-hackathon): verify actual `creative_stats` column names against production schema** — code has defensive fallbacks but a schema mismatch on live query is the most likely failure mode. `bq_ads.py` has an inline comment with the exact `INFORMATION_SCHEMA.COLUMNS` query to verify with.

### Longevity filter (LongevityAgent)
- [x] Pure Python, no LLM — flags ads running 90+ days with no stop-date
- [x] Tested — 6 winners out of 50 in stub run

### Pattern extraction (AnalyzeAgent)
- [~] Gemini 2.5 long-context + vision prompt (reads N ads' copy + images in one shot)
- [~] Returns typed `list[Pattern]` with category, description, frequency %, evidence ad IDs
- [~] JSON-fence stripping + graceful failure returning `[]`
- [ ] Live tested with real Gemini API key
- [ ] Retry logic on JSON parse failure

### Gap analysis (GapAgent)
- [~] Gemini 2.5 text prompt comparing user's ads vs winning patterns
- [~] Returns prioritized `list[GapItem]`
- [ ] Live tested with real Gemini

### Creative generation (CreateAgent)
- [~] Gemini 2.5 for copy (hook, body, CTA, image prompt, rationale) — 3 concepts in one call
- [~] Nano Banana (Gemini 2.5 Flash Image) for images — parallel generation
- [~] Writes PNGs to `generated_creatives/`
- [ ] Live tested with real Gemini + Nano Banana

### Executive summary (ReportAgent)
- [~] Gemini 2.5 CMO-style writer
- [~] Structured output: headline / what's working / top 3 moves / what NOT to do
- [ ] Live tested with real Gemini

### Orchestration
- [x] Functional pipeline: `agents/orchestrator.py` (currently used by FastAPI)
- [x] ADK SequentialAgent wrapper: `agents/adk_pipeline.py`
- [x] All 6 agents wrapped as `BaseAgent` subclasses with `_run_async_impl` yielding Events
- [x] State passing via `state_delta` verified end-to-end for first 2 nodes (Ingest -> Longevity)
- [~] Full 6-node ADK run needs Gemini key to validate
- [ ] FastAPI wired to `run_via_adk` instead of `Orchestrator`

### Storage (mandatory Cloud Service requirement)
- [x] `LocalJsonStore` - always-works fallback, writes to `data/analyses/*.json`
- [~] `FirestoreStore` - code written, needs GCP project ID + auth
- [x] `get_store()` factory picks based on `GCP_PROJECT_ID` env var
- [x] Analyses auto-saved after each `/analyze` request
- [~] Live tested with Firestore

### Web layer (FastAPI + HTMX + Tailwind)
- [x] `GET /` - landing form with brand + competitors + industry hint + creative toggle
- [x] `POST /analyze` - runs pipeline, returns HTMX report fragment
- [x] `GET /history` - lists recent analyses
- [x] `GET /report/{id}` - view saved report
- [x] `GET /creatives/{filename}` - serves generated PNGs with path-traversal guard
- [x] `GET /healthz` - includes `storage_backend` name for debugging
- [x] `templates/index.html` - form with loading spinner
- [x] `templates/report.html` - executive summary + stats + patterns + gaps + creatives grid + competitor breakdown
- [x] `templates/report_page.html` - standalone wrapper for /report/{id}
- [x] `templates/history.html` - clickable list
- [x] `templates/error.html`
- [ ] Live tested via browser

### Docs
- [x] `README.md` with quick-start, arch diagram, demo script, Google tech mapping
- [x] `CONTEXT.md` for session handoff
- [x] `STATUS.md` (this file)
- [x] `PLAN.md` for next steps

---

## Phase B - Deferred (post-8PM enhancements)

- [ ] **Commercial ad data via Kaggle CSV -> BigQuery upload** (`DATA_SOURCE=bq_kaggle`)
- [ ] Meta Ad Library LIVE via user token (`DATA_SOURCE=meta_live`)
- [ ] MCP Toolbox for Databases exposing BQ to agents (LLM tool-calling to query BQ)
- [ ] Cloud Run deployment with public URL
- [ ] Firebase Storage for generated creatives (instead of local disk)
- [ ] Looker Studio embed for creative performance dashboard
- [ ] Google Ads Transparency Center + TikTok Ad Library ingestion
- [ ] Veo for video-ad generation
- [ ] Slack/WhatsApp notifications on competitor new-ad launch
- [ ] Wire FastAPI to `run_via_adk` (currently uses functional orchestrator)
- [ ] Fine-tune JSON schema output via `response_mime_type="application/json"` + `response_schema`
- [ ] Retry logic on Gemini JSON parse failure
- [ ] Rate limiting on `/analyze` endpoint
- [ ] User auth (Firebase Auth) so history is per-user

---

## Tests

```bash
cd /Users/s0g09hc/Documents/swati/adintel
.venv/bin/python -m pytest tests/ -v
# (uses local venv directly; avoids `uv run` cert-fetch issues off-VPN)
```

Current: `9 passed`

- `test_ingest_returns_ads` — IngestAgent parallel fetch (via dispatcher → meta_stub)
- `test_longevity_filters_winners` — date filtering
- `test_stub_is_deterministic` — same brand → same ads across runs
- `test_political_row_mapping_full_schema` — realistic BQ row → Ad
- `test_political_row_mapping_sparse_row` — handles NULLs gracefully
- `test_creative_type_mapper` — ad_type string → CreativeType enum
- `test_synthesised_body_text_carries_signal` — mapper preserves signal for Gemini
- `test_kaggle_row_mapping_with_typical_columns` — Kaggle-shape row → Ad
- `test_kaggle_row_mapping_falls_back_on_missing_columns` — unknown schema → sensible defaults
