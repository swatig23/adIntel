# AdIntel - Build Status

**Snapshot:** 2026-09-03, 1:35 PM IST (personal laptop) + merged 9 PM IST (work laptop)
**Updated:** 2026-09-11 -- GCP project migration, landing page redesign, Nano Banana wording fix, evidence-backed gaps + Creative DNA scorecard, curated-visual demo data source (see "Stabilization pass" and "Feature additions" sections below)
**Real deadline:** Sep 9 final checkpoint, Sep 10 lock (see CONTEXT.md/PLAN.md for corrected Patchamomma 2026 timeline)

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
- [x] `DATA_SOURCE` env var with values: `meta_stub` | `bq_political` | `meta_live` | `bq_kaggle` | `bq_kaggle_transcripts` | `curated_visual`
- [x] `clients/bq_ads.py` — queries `bigquery-public-data.google_political_ads.creative_stats` (bq_political) or a user-owned Kaggle table (bq_kaggle / bq_kaggle_transcripts)
- [x] `clients/curated_visual.py` — **new (2026-09-11)**: reads a local, permissioned JSON corpus (`demo_ads.json`) + local image assets (`demo_assets/`) for a reliable, no-network demo path. Path-traversal safe (`_safe_local_image_url` rejects any `image_path` outside the asset dir). Documented in `DEMO_DATASET.md`. 2 new unit tests, both green.
- [x] `clients/ads.py` dispatcher module (routes on `DATA_SOURCE`)
- [x] `_normalize_table_id()` in `bq_ads.py` accepts both `project:dataset.table` (BQ console/CLI colon style) and `project.dataset.table` (dot, required for SQL backtick refs) — fixed 2026-09-05
- [x] 8 unit tests for BQ mappers — all green
- [x] **Live project migrated**: `.env` now points `GCP_PROJECT_ID` + `BQ_KAGGLE_TABLE` at `project-47457978-49f4-4e71-9a0` (the new billed project holding the Kaggle transcripts dataset). Logs confirm queries hit the new project, not the old `gen-lang-client-0516852331`. Live query itself is currently blocked by a VPC Service Controls org policy in the sandbox test network — config is correct, network access needs verifying from an approved environment.

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
- [x] **Live tested with real Gemini** 
- [x] **Evidence-backed citations (2026-09-11)**: `GapAgent._parse` now validates every `evidence_ad_ids` citation Gemini returns against the matched `Pattern`'s real `evidence_ad_ids` -- invented/hallucinated ad IDs are silently dropped, falling back to the pattern's own real evidence if Gemini cites nothing valid. Added `opportunity_score` (deterministic 0-100, computed from prevalence + user gap + evidence strength -- Gemini writes the advice, not the score) and `action_variants` (3 concrete tactical variants per gap). 2 new unit tests in `test_gap_evidence.py`, both green.

### Creative generation (CreateAgent)
- [x] Gemini for copy (hook, body, CTA, image prompt, rationale) — concepts in one call
- [x] **PIL Styled Card Renderer**: Instant local fallback (`_draw_fallback_card`) when free-tier API image quota is limit 0
- [x] Writes PNGs to `generated_creatives/`
- [x] **Live tested** 
- [x] **UI wording fixed (2026-09-05)**: removed all user-visible "Nano Banana" claims from `report.html`/`index.html` — the app never claims Nano Banana generated the fallback images. Copy now reads "Generate 3 fresh ad creatives" and "AI-generated concepts informed by winning competitor patterns." `GEMINI_IMAGE_MODEL` config and the real Gemini image-gen attempt are both still intact; the app still tries live Nano Banana generation first and only falls back to the PIL renderer when quota/API fails.

### Executive summary (ReportAgent)
- [x] Gemini CMO-style writer
- [x] Structured output: headline / what's working / top 3 moves / what NOT to do
- [x] **Live tested with real Gemini** ✅

### Orchestration
- [x] Functional pipeline: `agents/orchestrator.py` (fallback backend)
- [x] ADK SequentialAgent wrapper: `agents/adk_pipeline.py`
- [x] All 6 agents wrapped as `BaseAgent` subclasses
- [x] Full 6-node run validated 
- [x] **FastAPI now routes through ADK by default** (`ADK_ENABLED=true` in config, toggle in `.env` to fall back to functional Orchestrator instantly if needed). Confirmed via `/healthz` -> `"orchestration_backend":"adk"`. Both backends tuned identically (per_brand_limit=25, max_images=3, 2s inter-stage pause for free-tier rate limits).
- [ ] TODO: live end-to-end test of the ADK path with real Gemini calls returning actual patterns/gaps/creatives. As of the 2026-09-05 stabilization pass, the ADK path was confirmed to run all 6 nodes cleanly end-to-end via `/analyze` (HTTP 200, graceful zero-ads degradation logged at every stage) -- but no `GOOGLE_API_KEY` was available in that sandbox, so the Gemini-calling stages (Analyze/Gap/Create-copy/Report) were not exercised with real model output this pass.

### Storage
- [x] `LocalJsonStore` — fallback backend, writes to `data/analyses/*.json`, always works, zero setup
- [x] `FirestoreStore` — code written, activates automatically when `GCP_PROJECT_ID` is set; gracefully falls back to `LocalJsonStore` on any init/query error (never a hard dependency)
- [x] `get_store()` factory picks based on `GCP_PROJECT_ID` env var
- [x] **Live project migrated**: Firestore now correctly targets `project-47457978-49f4-4e71-9a0` (confirmed in logs), not the old `gen-lang-client-0516852331`. No code change was needed here — storage.py already followed `GCP_PROJECT_ID` correctly, this was purely an `.env` fix.

### Web layer (FastAPI + HTMX + Tailwind)
- [x] `GET /` — landing form — **live tested, 200 OK**
- [x] **Landing page redesigned (2026-09-05)**: `index.html` rebuilt into a full SaaS-style page — compact header with a real "LIVE DATA · BigQuery" / "DEMO MODE" status badge (`_live_status_label()` in main.py), hero section with headline/subhead/CTA, 3-step value prop (Discover/Decode/Create), metrics strip pulling real numbers from the latest saved analysis via `_latest_metrics()` (falls back to `--` placeholders when nothing has run yet, never fabricates numbers), the same analysis form (unchanged endpoint/fields/behavior), and an accurate Google-stack footer (ADK · Gemini · BigQuery · Cloud Run — dropped the old false "Firebase" claim since Firestore isn't guaranteed active).
- [x] `POST /analyze` — runs pipeline, returns HTMX report fragment — **live tested, 200 OK**
- [x] `report.html` polish (2026-09-05): added a small "Competitor ads → Winning patterns → Strategic gaps → Fresh creatives" pipeline strip; Nano Banana wording removed (see Creative generation section above). No backend response schema changes.
- [x] `GET /history` — lists recent analyses
- [x] `GET /report/{id}` — view saved report
- [x] `GET /creatives/{filename}` — serves generated PNGs — **live tested, 200 OK**
- [x] `GET /healthz` — **live tested, 200 OK**
- [x] All templates in `src/adintel/templates/`
- [x] `TemplateResponse` calls updated for Starlette/FastAPI v1.6+ compatibility (keyword args)
- [x] **App boots and serves requests on `http://127.0.0.1:8000`**

### Docs
- [x] `README.md` with quick-start, arch diagram, demo script, Google tech mapping
- [x] `CONTEXT.md` for session handoff
- [x] `STATUS.md` (this file)
- [x] `PLAN.md` for next steps
- [x] `TROUBLESHOOTING.md`

---

## Stabilization pass (2026-09-05) -- deadline-critical fixes, no architecture changes

Context: the Kaggle dataset was migrated to a new billed GCP project
(`project-47457978-49f4-4e71-9a0`) but the app was still silently querying
the old project (`gen-lang-client-0516852331`), and Nano Banana image
generation was unavailable (free-tier image quota is 0). This pass fixed
both without touching the 6-agent pipeline, ADK wiring, or any backend
response schema.

1. **BigQuery + Firestore project migration**
   - `.env` / `.env.example` now point `GCP_PROJECT_ID` and `BQ_KAGGLE_TABLE`
     at the new project.
   - Added `_normalize_table_id()` in `clients/bq_ads.py` so
     `BQ_KAGGLE_TABLE` accepts both `project:dataset.table` (BQ console/CLI
     colon style) and `project.dataset.table` (dot, required for SQL
     backtick references) -- fixes a latent bug that would have produced
     broken SQL if a user pasted the colon form straight from the console.
   - Firestore already read `GCP_PROJECT_ID` correctly in `storage.py` --
     no code change needed, just the `.env` fix. Confirmed via live logs
     that both BigQuery and Firestore now target the new project.
   - Firestore remains fully optional: any init/query failure logs a
     warning and falls back to `LocalJsonStore` automatically, dev never
     breaks.

2. **Nano Banana wording accuracy**
   - Removed every user-visible "Nano Banana" claim from `report.html` and
     `index.html`. "Generate 3 fresh ad creatives with Nano Banana" ->
     "Generate 3 fresh ad creatives"; "Generated with Nano Banana, informed
     by winning patterns above." -> "AI-generated concepts informed by
     winning competitor patterns."
   - `CreateAgent._draw_fallback_card` (the PIL-based fallback renderer)
     is unchanged and still the intentional, working fallback when live
     image generation fails on quota. `GEMINI_IMAGE_MODEL` config and the
     live Nano Banana attempt are both still intact -- app still tries
     real image gen first, falls back gracefully.

3. **Landing page redesign** (`index.html`) -- see Web layer section above.

4. **Report page polish** (`report.html`) -- see Web layer section above.

5. **Test fixes**
   - `tests/test_smoke.py` and `tests/test_longevity_skip_filter.py` were
     silently relying on `.env` defaulting to `DATA_SOURCE=meta_stub` /
     `BQ_SKIP_LONGEVITY_FILTER=false`. Once `.env` was updated to point at
     the new project (which uses `bq_kaggle_transcripts` +
     `BQ_SKIP_LONGEVITY_FILTER=true`), those tests started failing due to
     env leakage, not a real bug. Fixed by pinning the exact env vars each
     test needs and clearing the `get_settings()` lru_cache before
     asserting.

6. **Local dev environment**
   - Discovered the local `.venv` was missing `google-cloud-bigquery`
     (already declared in `pyproject.toml`/`uv.lock` -- pure venv drift,
     not a dependency change). Reinstalled via `uv pip install` with the
     Walmart internal index.

**Result:** all 31 tests pass. `/analyze`, `/creatives/{filename}`, and
`/healthz` all verified returning HTTP 200 in a live local run. BigQuery
live query is currently blocked by a VPC Service Controls org policy in
the sandbox network used for this stabilization pass (confirms the config
is correct -- it's hitting the new project -- but actual data return needs
verifying from an approved network). No `GOOGLE_API_KEY` was available in
this sandbox, so Gemini-dependent stages (Analyze/Gap/Create-copy/Report)
could not be live-tested end-to-end this pass -- they degrade gracefully
with clear warnings when ungated, not crashes, but need a real key +
network access for a true end-to-end verification before demo day.

---

## Feature additions (2026-09-11) -- landed on top of the stabilization pass

These arrived in a separate commit (`776b5cf "refactor 2"`) pushed straight
to `origin/main_master_merge` after the stabilization pass above. Reviewed
and verified alongside the STATUS.md/PLAN.md refresh:

1. **Creative DNA scorecard** (`src/adintel/creative_dna.py`, new model
   `CreativeDNA` in `models.py`): deterministic, explainable feature
   extraction per ad (hook type, social proof, offer, urgency, product
   demo, CTA/hook/offer/visual strength scores 1-10) using regex/keyword
   heuristics on ad copy -- no LLM call, no hallucination risk. Compares
   the user's ads vs. competitor average across 6 dimensions in a new
   "Competitive Creative DNA" table on the report page, plus a "dominant
   competitor play" callout when every competitor shares a signal the
   user doesn't. Explicitly labeled as creative signals, not performance
   predictions (CTR/conversion/ROAS) -- avoids overclaiming.
2. **Evidence-backed gap recommendations** (`agents/gap.py`,
   `report_dashboard.py`, `report.html`): each gap now shows an
   "Opportunity {score}/100" badge and a "Why this recommendation?"
   disclosure with the actual supporting competitor ad cards (image,
   copy, CTA, days-active, source link) pulled from real `evidence_ad_ids`
   -- Gemini's citations are validated against real pattern evidence
   before being trusted (see GapAgent update above). 3 tactical
   "variant" ideas per gap, also behind a disclosure.
3. **Curated visual demo data source** (`clients/curated_visual.py`,
   `DEMO_DATASET.md`, `demo_ads.json`, `demo_assets/`): a 6th
   `DATA_SOURCE` option for a reliable, no-network demo path using a
   small hand-picked JSON corpus + local image assets, with path-traversal
   protection on asset serving. Useful as a fallback if live BigQuery
   access is still blocked (VPC Service Controls, see Stabilization pass
   above) on demo day.
4. **Repo hygiene fix**: the commit that introduced the above also
   accidentally committed **unresolved git merge-conflict markers**
   (`<<<<<<< Updated upstream` / `=======` / `>>>>>>> Stashed changes`)
   into `.env.example` around the `DATA_SOURCE` default line. This did
   not break the running app (pydantic-settings just ignored the stray
   comment lines), but it's broken repo hygiene and confusing for anyone
   copying `.env.example` fresh. **Fixed**: resolved cleanly, keeping
   `DATA_SOURCE=bq_kaggle_transcripts` as the documented default and
   folding in the `curated_visual` option description. Verified no other
   conflict markers exist anywhere else in the repo.

**Result:** 37 tests pass (up from 31 after the stabilization pass -- 6
new tests: 2 for curated_visual, 2 for gap evidence validation, plus
report_dashboard test expansions for the scorecard/evidence helpers).

---

## What's been done this session (Sept 3 mid-day)

1. **End-to-End Pipeline Verification**: Executed `POST /analyze` for Warby Parker vs Ray-Ban, Zenni Optical — generated full competitive report + gaps (P1-P5).
2. **Local PIL Card Fallback**: Added `_draw_fallback_card` in `CreateAgent` so creative concept cards render in **1ms** if free-tier image API quota is hit.
3. **Multi-Model Fallback**: Added automatic failover across `gemini-3.5-flash`, `gemini-3.1-flash-lite`, and `gemini-flash-lite-latest` in `clients/gemini.py`.
4. **Multimodal Image Fix**: Fixed `generate_from_multimodal` with `follow_redirects=True` & MIME validation for image URLs.
5. **AnalyzeAgent Fallback**: Added automatic text-copy fallback if image processing hits server load spikes.

---

## Next Steps

1. **Get a real `GOOGLE_API_KEY` into `.env` on the actual demo machine/network**
   and re-run the full BMW/Audi/AutoZone smoke test end-to-end (Analyze/Gap/
   Create-copy/Report stages were not live-verified in the sandbox used for
   the 2026-09-05 stabilization pass -- no key was available there).
2. **Verify live BigQuery query access from an approved network/project** --
   the sandbox used for the stabilization pass hit a VPC Service Controls
   org policy block; config is confirmed correct (new project targeted),
   but actual row-level data return is still unverified live. If it stays
   blocked, `DATA_SOURCE=curated_visual` (see Feature additions above) is a
   ready fallback for a reliable no-network demo.
3. **Populate `demo_ads.json` / `demo_assets/` with a few real, permissioned
   competitor ads** if the curated_visual fallback path is going to be used
   live -- currently near-empty scaffolding.
4. **Test Second Scenario**: Run a second vertical test (e.g. `Notion` vs
   `Coda, Airtable, Obsidian`) once the above is confirmed working.
5. **Polish & Demo Prep**: Pre-baked demo brand combos & video script outline.
6. **Record 3-Minute Demo Video** (Step 10 in `PLAN.md`).
7. **Submit to Devpost** (Step 11 in `PLAN.md`).

---

## Tests

```bash
.venv/bin/python -m pytest tests/ -v
```

Current: `37 passed` on Python 3.12.12 (as of 2026-09-11, after the feature additions on top of the stabilization pass)
