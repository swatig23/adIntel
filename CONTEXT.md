# AdIntel - Session Context Handoff

**Purpose:** If token limits kill this chat session, a fresh session should be
able to read this file + the codebase and pick up seamlessly.

**Last updated:** 2026-09-03, ~2:30 AM IST
**Deadline:** 8 PM IST today (Sept 3, 2026)
**User:** swati (backend dev @ Walmart, Warehouse Management Systems)

---

## 1. What is this project?

**AdIntel** — a competitor ad-library copilot for SMBs.

Users enter their brand name + 3-10 competitor names. The system:
1. Pulls every active ad each competitor is running (Meta Ad Library API)
2. Flags "proven winners" (ads running 90+ days = Meta auction says they're profitable)
3. Uses Gemini 2.5 long-context + vision to extract cross-ad patterns
4. Compares user's ads vs winning patterns; produces prioritized gap list
5. Generates 3 fresh ad creatives via Nano Banana (Gemini 2.5 Flash Image)
6. Writes an executive summary

**For a Google Cloud hackathon** ("Google Patchamamma"-ish, likely internal/GDG).
Guidelines summary:
- Must use Google/Gemini tech stack
- MUST use at least one Cloud Service (BigQuery, Firestore, etc.)
- Data-driven (must use real public data)
- ADK for multi-agent = strongly encouraged
- MCP Toolbox for Databases = strongly encouraged
- Cloud Run deployment = strongly encouraged (2 free deploys via AI Studio)
- Free `$300` GCP trial credits

---

## 2. How we got here (idea evolution)

The user rejected these before landing on AdIntel:

| Idea | Reason rejected |
|------|-----------------|
| Supply chain / logistics (adjacent to WMS) | Not exciting to her |
| Healthcare, DevTools, Sustainability, EdTech | Not exciting |
| ColdCraft (deep-research cold email agent) | Interested but preferred SMB angle |
| ClipFactory (long video → shorts) | Not chosen |
| BidBuddy (Indian gov tender assistant) | Not chosen |
| TaxDost, WhatsAppWaale, LeadPilot, PaisaFlow, KaamKhoj, ComplianceKaka | All involved sensitive financial/transaction data — rejected on trust barrier |
| DhandhaCreative, ReviewRakshak, PosterKart | SMB but weak on "existing public data" requirement |
| MenuMind v2 (restaurant menu optimizer with Zomato + AgMarknet) | Solid but she opted for global angle instead |
| YelpSense (SMB reputation using Yelp Open Dataset) | Close 2nd |
| **AdIntel (WINNER)** | Best combo: real public data (Meta Ad Library), agentic + multimodal + generative, high revenue ceiling, global market |

She's open to non-India markets. Prefers B2B/SaaS with clear revenue path.
Comparable products: AdSpy ($99/mo), Anstrex, PowerAdSpy, Motion.ai ($299/mo),
Foreplay. None are truly agentic + generative — that's our wedge.

---

## 3. Tech stack

- **Python 3.12** (via `uv` — Walmart index configured)
- **FastAPI** backend, **HTMX + Tailwind** frontend (no build step)
- **google-genai** 0.3+ (Gemini 2.5 Flash text/vision + Gemini 2.5 Flash Image aka Nano Banana)
- **google-adk** 2.8.0 (SequentialAgent + BaseAgent wrappers around our 6 agents)
- **google-cloud-firestore** (persistence, with LocalJsonStore fallback)
- **httpx** for Meta Ad Library API
- **loguru** for logging
- **pydantic** + **pydantic-settings** for models & config

---

## 4. Architecture

```
Web UI (HTMX + Tailwind)
        v
FastAPI (src/adintel/main.py)
        v
Orchestrator (functional pipeline: src/adintel/agents/orchestrator.py)
   OR
SequentialAgent (ADK pipeline: src/adintel/agents/adk_pipeline.py)
        v
+----------+----------+----------+----------+----------+----------+
| Ingest   | Longevity| Analyze  | Gap      | Create   | Report   |
| Agent    | Agent    | Agent    | Agent    | Agent    | Agent    |
+----------+----------+----------+----------+----------+----------+
      v         v         v          v          v          v
  MetaAdLib   date-math Gemini2.5   Gemini    Nano       Gemini
  API        (no LLM)  vision +    2.5       Banana     2.5
  (stub OR             long-ctx    text                  text
  live)
        v
Storage (Firestore OR LocalJsonStore) - src/adintel/storage.py
Generated PNGs -> generated_creatives/
```

**IMPORTANT:** Both orchestrator implementations exist. FastAPI app currently
uses the functional one (`agents/orchestrator.py`). The ADK version
(`agents/adk_pipeline.py`) is tested to work for the first 2 nodes with stub
data and is production-ready but hasn't yet been wired into FastAPI (see
enhancement list).

---

## 5. File layout

```
/Users/s0g09hc/Documents/swati/adintel/
  pyproject.toml              # deps + pytest config
  .python-version             # 3.12
  .env.example                # copy to .env, paste GOOGLE_API_KEY
  .gitignore
  README.md                   # user-facing docs
  STATUS.md                   # what's done vs not
  PLAN.md                     # what to do next (this session or resumed)
  CONTEXT.md                  # THIS FILE
  scripts/
    test_gemini_connection.py # Standalone Gemini/Nano-Banana connectivity check
  TROUBLESHOOTING.md          # Self-serve fixes for solo work (no Code Puppy on personal laptop)
  src/adintel/
    __init__.py
    main.py                   # FastAPI app (/, /analyze, /history, /report/{id}, /healthz, /creatives/{name})
    config.py                 # pydantic-settings, reads .env
    models.py                 # Ad, Competitor, Pattern, GapItem, GeneratedCreative, AnalysisRequest, AnalysisReport
    storage.py                # LocalJsonStore + FirestoreStore + get_store() factory
    clients/
      __init__.py
      meta_ads.py             # fetch_ads_for_brand() — stub + live modes
      gemini.py               # generate_text, generate_from_multimodal, generate_image
    agents/
      __init__.py
      ingest.py               # IngestAgent (Meta API)
      longevity.py            # LongevityAgent (90+ day winner filter)
      analyze.py              # AnalyzeAgent (Gemini long-ctx pattern extraction)
      gap.py                  # GapAgent (user vs winners)
      create.py               # CreateAgent (Nano Banana + Gemini copy)
      report.py               # ReportAgent (executive summary)
      orchestrator.py         # Functional Orchestrator - CURRENTLY USED by FastAPI
      adk_pipeline.py         # ADK SequentialAgent wrapper - PARTIALLY TESTED
    templates/
      index.html              # landing form
      report.html             # results (HTMX partial + standalone via include)
      report_page.html        # standalone view for /report/{id}
      history.html            # /history list
      error.html              # 500 page
    static/                   # (empty, ready for assets)
  tests/
    test_smoke.py             # 3 tests, all green: ingest, longevity, deterministic stub
  data/analyses/              # LocalJsonStore output (auto-created)
  generated_creatives/        # Nano Banana output PNGs
```

---

## 6. Environment setup (already done in .venv/)

```bash
cd /Users/s0g09hc/Documents/swati/adintel
uv sync --python 3.12 \
  --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple \
  --allow-insecure-host pypi.ci.artifacts.walmart.com
```

**.env NOT yet created.** User needs to:
1. Copy `.env.example` -> `.env`
2. Get Google AI Studio API key at https://aistudio.google.com/apikey (free)
3. Paste as `GOOGLE_API_KEY=...`
4. (Optional) Sign up GCP, create project, put `GCP_PROJECT_ID=...` for Firestore

By default: `USE_META_STUB=true` (works offline, no Meta token needed).

---

## 7. What's been tested successfully

- `uv sync` installs all deps clean on Python 3.12
- `uv run pytest tests/` — 3/3 passing (Ingest + Longevity + deterministic stub)
- Ad-hoc test of ADK SequentialAgent with `IngestNode` + `LongevityNode` — passes 25 ads through, produces 6 winners, state propagates via `state_delta`

## 8. What's NOT yet tested (blocked on user's Gemini key)

- Real Gemini text calls (AnalyzeAgent, GapAgent, ReportAgent)
- Real Gemini vision on ad images
- Real Nano Banana image generation
- Full end-to-end orchestrator run
- Full end-to-end ADK pipeline run
- FastAPI `/analyze` endpoint end-to-end
- Firestore save/load (needs GCP project)

---

## 9. Known issues / risks

1. **LLM JSON parsing** — Gemini sometimes returns malformed JSON despite
   `Return ONLY the JSON array`. `AnalyzeAgent` and `GapAgent` have basic
   markdown-fence stripping but no retry logic. If parsing fails, they
   return `[]`. May need `response_mime_type="application/json"` in the
   `GenerateContentConfig`.
2. **Nano Banana rate limits** on free tier — 3 image gens per pipeline
   run should be fine but might hit limits after 10-20 demo runs.
3. **Meta Ad Library live API** — not usable for hackathon (Meta app
   approval takes 2-6 weeks). Stub covers the demo.
4. **SequentialAgent deprecation warning** — ADK 2.8 says it's deprecated
   in favor of `Workflow`, but `Workflow` "cannot yet be used as an LlmAgent
   sub-agent". Ignore for hackathon.
5. **Pydantic models in ADK session state** — works fine with
   `InMemorySessionService` (no serialization). Would need `.model_dump()`
   if we ever swap to `VertexAiSessionService`.
6. **FastAPI uses `Orchestrator` not `run_via_adk`** — the ADK path is
   built but not wired into the web layer. See PLAN.md.

---

## 10. Deviations from the original AdIntel pitch

| Original pitch | Reality shipped |
|---|---|
| Meta Ad Library LIVE API | Stub with realistic deterministic synthetic data. Live API code exists but untested. Requires Meta app approval (10 min ID verification, not 2-6 weeks as I earlier stated). |
| BigQuery for ad history | **DECISION 2026-09-03 ~2:35 AM**: adding BQ integration overnight using `bigquery-public-data.google_political_ads` (Google's own transparency dataset). Real 3M+ ads with copy, spend, impressions, targeting. Judge-story flips from "synthetic" to "data-driven with Google's own public dataset". Config toggle `DATA_SOURCE=bq_political` will switch backends. Commercial ads can be added later via Kaggle upload to BQ (`DATA_SOURCE=bq_kaggle`) or Meta live API (`DATA_SOURCE=meta_live`). |
| MCP Toolbox for Databases | Not built (deferred to Phase B) |
| Cloud Run deploy with live URL | Not built (deferred to Phase B) |
| Looker Studio embed | Not built (deferred to Phase B) |
| Google Ads / TikTok Ad Library ingestion | Not built (post-hackathon) |
| ADK-native orchestration | Built but not wired into web app (both orchestrators exist) |
| Firebase Storage for creatives | Not built - saves to local `generated_creatives/` |

**All Phase-B items are documented in PLAN.md.**

### Data-source strategy (locked as of 2026-09-03)

AdIntel uses a pluggable data source controlled by the `DATA_SOURCE` env var:

| Value | Backend | Ships when |
|---|---|---|
| `meta_stub` (default) | Deterministic synthetic ads via seeded random | Now (fallback for zero-setup) |
| `bq_political` | Queries `bigquery-public-data.google_political_ads` via BigQuery | Overnight build, live tomorrow AM once user provides `GCP_PROJECT_ID` |
| `meta_live` | Meta Ad Library v18 API | Code written, live whenever user gets a Meta token |
| `bq_kaggle` | Queries a user-owned BQ dataset loaded from Kaggle | Post-hackathon commercial swap |

All backends return identical `list[Ad]` so downstream agents don't change.

---

## 10.5. Personal laptop migration (2026-09-03)

User hit a hard blocker: Code Puppy requires Walmart VPN, and Gemini API
calls from the work laptop failed with `SSL: CERTIFICATE_VERIFY_FAILED`
when VPN cert-inspection was in the path. User explicitly declined any
Walmart-cert workaround (correct call — don't mix personal projects with
corporate infra) and is migrating the whole `adintel/` project to a
personal laptop where **Code Puppy will NOT be available**.

Consequences for how this project is documented:
- `TROUBLESHOOTING.md` added — self-serve debugging without an AI assistant
- `scripts/test_gemini_connection.py` added — isolates API/network issues
  from pipeline logic issues, runnable standalone
- All docs (`PLAN.md`, `STATUS.md`) must be self-sufficient: assume the
  user is executing steps alone, no chat-based help available
- If a NEW Code Puppy session ever resumes on the personal laptop, that's
  a bonus, but the project must be completable without one

## 11. User's constraints & preferences

- Walmart backend dev — comfortable with Python, APIs, backend orchestration
- 4-5 focused work hours available today, split across day
- Has 8 PM IST checkpoint TODAY
- Picked scope: "Cut BQ+MCP+CloudRun, ship safe"
- No GCP account yet (will sign up morning)
- No Google AI Studio key yet (will generate morning)
- Cross-cutting rules from Walmart environment (see initial system prompt):
  - `uv` + `--index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com`
  - No emojis in file writes (emoji filter is ENABLED)
  - Walmart VPN or Eagle WiFi required for Code Puppy
  - Cloud Run deploy: use launchpad sub-agent OR AI Innovation Lab
  - Windows installs: rewrite GitHub URLs to Walmart artifactory
  - No competitor-site scrapers for pricing/assortment (Amazon/Meta not affected here since Meta Ad Library is a public transparency tool)

---

## 12. If tokens die - resumption script

New session should:
1. `cd /Users/s0g09hc/Documents/swati/adintel && ls` — verify project intact
2. Read this CONTEXT.md and STATUS.md
3. Read PLAN.md for immediate next steps
4. `uv run pytest tests/` — verify baseline is still green
5. Ask user: "Do you have `GOOGLE_API_KEY` in `.env` yet?" and proceed from
   step 1 of PLAN.md accordingly
6. Do NOT re-scaffold anything. All 6 agents + storage + ADK wrapper exist.
7. Do NOT re-argue idea selection. AdIntel is locked in.
