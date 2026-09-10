# AdIntel

**Competitor Ad Intelligence Copilot for SMBs.**
Analyze recurring patterns in your competitors' ads, identify strategic gaps,
and generate fresh creatives informed by what actually works.

Built for the Google hackathon. Uses **Gemini 2.5** (long context + vision),
**Vertex AI** (Gemini 2.5 Flash Image) for on-demand creative visuals,
**BigQuery** with a Kaggle ad-transcript dataset for competitor data, and a
**Google ADK SequentialAgent** multi-agent pipeline.

---

## The pitch

Small businesses spend $500-5,000/mo on Meta/Google ads and burn 80% of
budget on bad creative. Existing competitive-intel tools (AdSpy, Anstrex,
PowerAdSpy — all $99-297/mo) are ugly dashboards with zero AI.

AdIntel:

1. Retrieves reference ads for your competitors from BigQuery (Kaggle ad-transcript dataset)
2. Uses **Gemini 2.5 long context** to extract recurring creative patterns across competitor ads
3. Uses **Gemini 2.5 vision** to analyze themes and messaging angles in ad copy
4. Compares your brand against those patterns; surfaces prioritized strategic opportunities
5. Generates 3 fresh creative concepts informed by the patterns; optionally renders a
   Vertex AI visual (Gemini 2.5 Flash Image) per card, on demand

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
BigQuery     Gemini     Gemini      Gemini     Gemini
(Kaggle      2.5        2.5         2.5        2.5
transcripts) (vision +  (text)      (text      (text)
             long ctx)              concepts)
```

Each agent lives in its own file under `src/adintel/agents/` and does one
job well. The Orchestrator wires them into a sequential pipeline.

---

## Quick start

### 1. Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- **Gemini auth — pick one:**
  - **Option A (AI Studio):** free API key from https://aistudio.google.com/apikey — easiest to start, limited image quota.
  - **Option B (Vertex AI, recommended):** a GCP project with Vertex AI API enabled and Application Default Credentials. Required for production image generation.
- *(Optional)* A Meta App with `ads_read` scope for live competitor data.
  Without it the app runs in **stub mode** with realistic synthetic data.

### 2. Install

```bash
cd adintel
uv sync --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
cp .env.example .env
```

### 3. Configure auth

**Option A — AI Studio API key:**
```bash
# In .env, set:
GOOGLE_API_KEY=AIzaSy...
```

**Option B — Vertex AI (recommended for image generation):**
```bash
# In .env, set:
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=global               # "global" is required for gemini-2.5-flash-image
# Leave GOOGLE_API_KEY blank.

# Then authenticate locally:
gcloud auth application-default login

# Enable the Vertex AI API on your project (one-time):
gcloud services enable aiplatform.googleapis.com
```
When `GOOGLE_API_KEY` is blank and `GCP_PROJECT_ID` is set, the app
automatically routes all Gemini calls through Vertex AI using ADC.
No extra flag or code change required.

### 4. Run

```bash
uv run uvicorn adintel.main:app --reload --port 8000
# open http://localhost:8000
```

### 5. Verify image generation is working

After running an analysis, click **Generate AI Visual · Billable →** on any
creative card. You will see a confirmation prompt before any API call is made.
On success the card image is replaced with a Gemini-generated visual.

To disable image generation entirely (e.g. cost-controlled environments):
```bash
# In .env:
IMAGE_GENERATION_ENABLED=false
```

### 6. (Later) Switch to live Meta data

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

| Layer                    | Service                                           |
|--------------------------|---------------------------------------------------|
| LLM reasoning            | Gemini 2.5 Flash (long context)                   |
| Multimodal analysis      | Gemini 2.5 Flash (vision on ad creatives)         |
| Image generation         | Gemini 2.5 Flash Image via Vertex AI              |
| Agent orchestration      | Google ADK SequentialAgent                        |
| Serverless compute       | Cloud Run                                         |
| Ad data                  | BigQuery                                          |
| State (optional)         | Firestore                                         |
| Creative storage         | Firebase Storage                                  |

---

## Demo script (3 minutes)

1. **0:00-0:20** — Problem: SMBs bleed cash on bad ads. Show a fake bad ad.
2. **0:20-0:40** — Open AdIntel. Type in "Warby Parker" as your brand,
   "Ray-Ban, Zenni Optical, GlassesUSA" as competitors.
3. **0:40-1:20** — Show the report loading: 75 ads retrieved, recurring
   patterns extracted by Gemini long-context.
4. **1:20-2:10** — Walk through the extracted patterns and the priority
   gaps. Highlight one specific insight: "top 3 winning ads all open
   with a rhetorical question in the first 8 words. You don't."
5. **2:10-2:50** — Scroll to 3 generated creative concepts. Emphasize: these
   were generated by Gemini, guided by the patterns. Click "Generate AI Visual"
   on any card for an on-demand Vertex AI image.
6. **2:50-3:00** — Close: "This costs $299/mo elsewhere. AdIntel does it
   better and generates the creatives too."

---

## What to build next (post-hackathon)

- MCP Toolbox for Databases to store historical pattern tracking in BigQuery
- Google Ads Transparency Center + TikTok Ad Library ingestion
- Video ad generation via Veo
- Automatic A/B test setup via Meta Marketing API
- Slack/WhatsApp notifications when a competitor launches a new ad
