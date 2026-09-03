# AdIntel - Build Status

**Snapshot:** 2026-09-03, 1:35 PM IST
**Deadline:** 8 PM IST today

Legend: `[x]` done & tested | `[~]` code written, needs live test | `[ ]` not started

---

## Phase A - Ship-safe MVP (locked scope for 8 PM)

### Foundation
- [x] `uv` project on Python 3.12 with deps installed & lockfile stable
- [x] `.gitignore`, `.env.example`, `.python-version`
- [x] Directory structure: `src/adintel/{agents,clients,templates,static}` — **reorganized from flat upload**
- [x] Pydantic models: `Ad`, `Competitor`, `Pattern`, `GapItem`, `GeneratedCreative`, `AnalysisRequest`, `AnalysisReport`
- [x] `Settings` (pydantic-settings) reading from `.env`
- [x] `clients/__init__.py` and `agents/__init__.py` package init files created
- [x] `pyproject.toml` updated: `pythonpath = ["src"]` for pytest
- [x] Datetime deprecation warnings cleaned up (timezone-aware UTC)
- [x] Git repo initialized, pushed to `https://github.com/swatig23/adIntel.git`

### API Key & Model Configuration
- [x] Google AI Studio API key obtained and set in `.env`
- [x] Model configured to fast active models: `gemini-3.5-flash` / `gemini-flash-latest` / `gemini-3.1-flash-lite`
- [x] `.env.example` & `config.py` defaults updated
- [x] Multi-model instant fallback implemented in `clients/gemini.py` (`_call_with_retry`)

### Gemini Connectivity & Performance Optimizations
- [x] `scripts/test_gemini_connection.py` — **text generation confirmed working** ("Hello to you, my friend.")
- [x] Automatic retry + 503/429 backoff handling
- [x] **Multi-model fallback**: switches seamlessly between `gemini-3.5-flash`, `gemini-3.1-flash-lite`, and `gemini-flash-lite-latest` if any single model endpoint experiences load spikes
- [x] **HTTP Image Fetching**: `follow_redirects=True` + MIME filtering for `generate_from_multimodal`
- [x] **Local PIL Fallback Card Renderer**: `CreateAgent._draw_fallback_card` generates styled 600x600 PNG creative cards in **1ms** if image API is quota-restricted

### Data ingestion (IngestAgent)
- [x] `fetch_ads_for_brand()` with backends
- [x] Stub mode: deterministic per-brand synthetic ads (25 per brand default)
- [x] Stub mode: realistic hook templates, CTAs, delivery windows
- [~] Live mode: Meta Ad Library v18 API - code written
- [~] BigQuery mode: `clients/bq_ads.py` — code written
- [x] Smoke test: tests green (fetch, deterministic, longevity filter)

### Data source dispatcher
- [x] `DATA_SOURCE` env var with values: `meta_stub` | `bq_political` | `meta_live` | `bq_kaggle`
- [x] `clients/bq_ads.py` — queries `bigquery-public-data.google_political_ads.creative_stats`
- [x] `clients/ads.py` dispatcher module (routes on `DATA_SOURCE`)
- [x] 6 unit tests for BQ mappers — all green

### Longevity filter (LongevityAgent)
- [x] Pure Python, no LLM — flags ads running 90+ days with no stop-date
- [x] Tested — flags winners (e.g. 13 winners across 50 ads)

### Pattern extraction (AnalyzeAgent)
- [x] Gemini long-context + vision prompt (reads N ads' copy + images in one shot)
- [x] Returns typed `list[Pattern]` with category, description, frequency %, evidence ad IDs
- [x] JSON-fence stripping + graceful failure returning `[]`
- [x] Automatic text copy fallback if multimodal image call encounters API 503 load
- [x] **Live tested with real Gemini API key** ✅

### Gap analysis (GapAgent)
- [x] Gemini text prompt comparing user's ads vs winning patterns
- [x] Returns prioritized `list[GapItem]`
- [x] **Live tested with real Gemini** ✅

### Creative generation (CreateAgent)
- [x] Gemini for copy (hook, body, CTA, image prompt, rationale) — concepts in one call
- [x] **PIL Styled Card Renderer**: Instant local fallback (`_draw_fallback_card`) when free-tier API image quota is limit 0
- [x] Writes PNGs to `generated_creatives/`
- [x] **Live tested** ✅

### Executive summary (ReportAgent)
- [x] Gemini CMO-style writer
- [x] Structured output: headline / what's working / top 3 moves / what NOT to do
- [x] **Live tested with real Gemini** ✅

### Orchestration
- [x] Functional pipeline: `agents/orchestrator.py` (currently used by FastAPI)
- [x] ADK SequentialAgent wrapper: `agents/adk_pipeline.py`
- [x] All 6 agents wrapped as `BaseAgent` subclasses
- [x] Full 6-node run validated ✅
- [ ] **Wire FastAPI to `run_via_adk` instead of `Orchestrator`** (Next afternoon step)

### Storage
- [x] `LocalJsonStore` — active, writes to `data/analyses/*.json`
- [~] `FirestoreStore` — code written, needs GCP project ID + auth
- [x] `get_store()` factory picks based on `GCP_PROJECT_ID` env var

### Web layer (FastAPI + HTMX + Tailwind)
- [x] `GET /` — landing form — **live tested, 200 OK**
- [x] `POST /analyze` — runs pipeline, returns HTMX report fragment — **live tested, 200 OK**
- [x] `GET /history` — lists recent analyses
- [x] `GET /report/{id}` — view saved report
- [x] `GET /creatives/{filename}` — serves generated PNGs
- [x] `GET /healthz` — **live tested, 200 OK**
- [x] All templates in `src/adintel/templates/`
- [x] `TemplateResponse` calls updated for Starlette/FastAPI v1.6+ compatibility (keyword args)
- [x] **App boots and serves requests on `http://127.0.0.1:8000`** ✅

### Docs
- [x] `README.md` with quick-start, arch diagram, demo script, Google tech mapping
- [x] `CONTEXT.md` for session handoff
- [x] `STATUS.md` (this file)
- [x] `PLAN.md` for next steps
- [x] `TROUBLESHOOTING.md`

---

## What's been done this session (Sept 3 mid-day)

1. **End-to-End Pipeline Verification**: Executed `POST /analyze` for Warby Parker vs Ray-Ban, Zenni Optical — generated full competitive report + gaps (P1-P5).
2. **Local PIL Card Fallback**: Added `_draw_fallback_card` in `CreateAgent` so creative concept cards render in **1ms** if free-tier image API quota is hit.
3. **Multi-Model Fallback**: Added automatic failover across `gemini-3.5-flash`, `gemini-3.1-flash-lite`, and `gemini-flash-lite-latest` in `clients/gemini.py`.
4. **Multimodal Image Fix**: Fixed `generate_from_multimodal` with `follow_redirects=True` & MIME validation for image URLs.
5. **AnalyzeAgent Fallback**: Added automatic text-copy fallback if image processing hits server load spikes.

---

## Next Steps (Afternoon plan)

1. **Wire ADK path into FastAPI** (Step 7 in `PLAN.md`):
   - Switch `POST /analyze` in `src/adintel/main.py` from `orchestrator.run` to `run_via_adk` to show `google-adk` framework usage for hackathon judges.
2. **Test Second Scenario**: Run a second vertical test (e.g. `Notion` vs `Coda, Airtable, Obsidian`).
3. **Polish & Demo Prep**: Pre-baked demo brand combos & video script outline.
4. **Record 3-Minute Demo Video** (Step 10 in `PLAN.md`).
5. **Submit to Devpost** (Step 11 in `PLAN.md`).

---

## Tests

```bash
uv run pytest tests/ -v
```

Current: `9 passed` on Python 3.12.13
