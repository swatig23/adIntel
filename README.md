# AdIntel

**Competitor Ad Library Copilot for SMBs.**
Learn from your competitors' proven-winner ads, then generate fresh creatives
that mimic what actually works.

Built for the Google hackathon. Uses **Gemini 2.5** (long context + vision),
**Nano Banana** (Gemini 2.5 Flash Image) for creative generation,
**Meta Ad Library API** for live competitor data, and a multi-agent pipeline
inspired by **Google ADK**.

---

## The pitch

Small businesses spend $500-5,000/mo on Meta/Google ads and burn 80% of
budget on bad creative. Existing competitive-intel tools (AdSpy, Anstrex,
PowerAdSpy — all $99-297/mo) are ugly dashboards with zero AI.

AdIntel:

1. Pulls every active ad your competitors are running (Meta Ad Library API)
2. Flags "proven winners" — ads Meta's auction has kept alive 90+ days
3. Uses **Gemini 2.5 long context + vision** to extract recurring patterns
   across dozens of winning ads in one shot
4. Compares your ads against those patterns; produces prioritized gaps
5. Generates 3 fresh creatives with **Nano Banana**, informed by the patterns

You get a full competitive report + ready-to-run ads in ~60 seconds.

---

## Architecture

```
        Web UI (HTMX + Tailwind)
                |
                v
        FastAPI on Cloud Run
                |
                v
        Orchestrator
    ____________|_______________________________
   /       /        |          |         \      \
  v       v         v          v          v      v
Ingest Longevity Analyze   Gap        Create  Report
Agent  Agent     Agent     Agent      Agent   Agent
  |               |         |          |        |
  v               v         v          v        v
Meta         Gemini     Gemini      Nano       Gemini
Ad Lib       2.5        2.5         Banana     2.5
API          (vision +  (text)      (image     (text)
             long ctx)              gen)
```

Each agent lives in its own file under `src/adintel/agents/` and does one
job well. The Orchestrator wires them into a sequential pipeline.

---

## Quick start

### 1. Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- A **Google AI Studio** API key (free): https://aistudio.google.com/apikey
- *(Optional)* A Meta App with `ads_read` scope for live competitor data.
  Without it the app runs in **stub mode** with realistic synthetic data.

### 2. Install

```bash
cd adintel
uv sync --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
cp .env.example .env
# then edit .env and paste your GOOGLE_API_KEY
```

### 3. Run

```bash
uv run uvicorn adintel.main:app --reload --port 8000
# then open http://localhost:8000
```

### 4. (Later) Switch to live Meta data

Get a Meta access token with `ads_read` scope:
1. Go to https://developers.facebook.com/apps and create an app
2. Add "Ad Library API" product
3. Generate a user access token with `ads_read` scope
4. Paste into `.env` as `META_ACCESS_TOKEN`
5. Set `USE_META_STUB=false`

---

## Project layout

```
adintel/
  pyproject.toml
  .env.example
  README.md
  src/adintel/
    __init__.py
    main.py               <- FastAPI app
    config.py             <- pydantic-settings
    models.py             <- Ad, Competitor, Pattern, GapItem, ...
    clients/
      meta_ads.py         <- Meta Ad Library API (live + stub)
      gemini.py           <- google-genai wrapper (text/vision/image)
    agents/
      __init__.py
      ingest.py           <- fetch competitor ads
      longevity.py        <- flag proven winners
      analyze.py          <- extract patterns (Gemini long-ctx + vision)
      gap.py              <- compare user vs winners
      create.py           <- generate creatives (Nano Banana)
      report.py           <- executive summary
      orchestrator.py     <- sequential pipeline
    templates/
      index.html          <- landing + form
      report.html         <- HTMX partial with results
      error.html
  tests/
    test_smoke.py         <- pipeline wiring without touching Gemini
  generated_creatives/    <- output PNGs (gitignored)
```

---

## Google tech used

| Layer                    | Service                                    |
|--------------------------|--------------------------------------------|
| LLM reasoning            | Gemini 2.5 Flash (long context)            |
| Multimodal analysis      | Gemini 2.5 Flash (vision on ad creatives)  |
| Image generation         | Gemini 2.5 Flash Image (Nano Banana)       |
| Agent orchestration      | Custom sequential (ADK-swappable)          |
| Serverless compute       | Cloud Run                                  |
| State (optional)         | Firestore                                  |
| Creative storage         | Firebase Storage                           |

---

## Demo script (3 minutes)

1. **0:00-0:20** — Problem: SMBs bleed cash on bad ads. Show a fake bad ad.
2. **0:20-0:40** — Open AdIntel. Type in "Warby Parker" as your brand,
   "Ray-Ban, Zenni Optical, GlassesUSA" as competitors.
3. **0:40-1:20** — Show the report loading: 75 ads analyzed, 22 winners
   flagged, patterns extracted by Gemini long-context.
4. **1:20-2:10** — Walk through the extracted patterns and the priority
   gaps. Highlight one specific insight: "top 3 winning ads all open
   with a rhetorical question in the first 8 words. You don't."
5. **2:10-2:50** — Scroll to 3 generated creatives. Emphasize: these were
   generated by Nano Banana, guided by the patterns, in 20 seconds.
6. **2:50-3:00** — Close: "This costs $299/mo elsewhere. AdIntel does it
   better and generates the creatives too."

---

## What to build next (post-hackathon)

- ADK wrapper around agents (SequentialAgent for tracing)
- MCP Toolbox for Databases to store historical winner tracking in BigQuery
- Google Ads Transparency Center + TikTok Ad Library ingestion
- Video ad generation via Veo
- Automatic A/B test setup via Meta Marketing API
- Slack/WhatsApp notifications when a competitor launches a new ad
