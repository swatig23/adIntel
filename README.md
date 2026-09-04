# AdIntel

**Competitor Ad Library Copilot for SMBs.**  
Learn from your competitors' proven-winner ads, extract cross-ad strategies, and generate fresh winning creative concepts.

Built for the Google Hackathon. Uses **Google ADK** (`google.adk`), **Gemini 3.5 / Flash** (long context + vision), **Nano Banana** (Gemini Flash Image) with 1ms PIL card fallback for creative rendering, and **BigQuery / Meta Ad Library** for competitive data ingestion.

---

## The Pitch

Small businesses spend $500–$5,000/month on Meta & Google ads and burn 80% of budget on bad creative. Existing competitive-intel tools (AdSpy, Anstrex, PowerAdSpy — all $99–$297/mo) are static dashboards with zero AI reasoning.

**AdIntel**:
1. **Ingests** competitor ads via Meta Ad Library API, BigQuery public datasets, or deterministic stub mode.
2. **Flags "proven winners"** — ads active for 90+ days in Meta's auction.
3. **Extracts cross-ad patterns** using **Gemini 3.5 Flash** (long-context vision + text) across all winning ads in one pass.
4. **Spotlights strategic gaps** comparing your brand's active ads against competitor winning patterns.
5. **Generates fresh ad concepts** with **Nano Banana** (Gemini Flash Image) and instant PIL card fallback rendering.
6. **Writes CMO-level executive summaries** for immediate action.

---

## Architecture

```
                 Web UI (FastAPI + HTMX + Tailwind)
                                 │
                                 ▼
                     Google ADK SequentialAgent
  ┌───────────────┬──────────────┼───────────────┬───────────────┬──────────────┐
  │               │              │               │               │              │
  ▼               ▼              ▼               ▼               ▼              ▼
IngestAgent LongevityAgent AnalyzeAgent      GapAgent       CreateAgent    ReportAgent
  │               │              │               │               │              │
  ▼               ▼              ▼               ▼               ▼              ▼
Meta Ad Lib   Pure Python    Gemini 3.5      Gemini 3.5      Nano Banana    Gemini 3.5
/ BigQuery   Winner Filter  Vision/Text     (Parallel Gap)  / PIL Card     Exec Summary
```

Each agent is modularly wrapped as a `google.adk.agents.BaseAgent` inside [`adk_pipeline.py`](file:///Users/shawttygarg/Documents/Projects/adIntel/src/adintel/agents/adk_pipeline.py). The FastAPI app routes requests through ADK (`ADK_ENABLED=true`), with an instant fallback to the functional [`orchestrator.py`](file:///Users/shawttygarg/Documents/Projects/adIntel/src/adintel/agents/orchestrator.py).

---

## Quick Start & Running the Application

### 1. Prerequisites
- Python 3.11+ (Python 3.12 recommended)
- [`uv`](https://docs.astral.sh/uv/) for high-speed package management
- A **Google AI Studio** API key (free): [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- *(Optional)* Google Cloud Project ID for BigQuery (`DATA_SOURCE=bq_political`) or Firestore persistence.

### 2. Installation & Configuration

```bash
# 1. Clone & enter directory
cd adintel

# 2. Create virtual environment & sync dependencies with uv
uv venv --python 3.12
uv sync

# 3. Create .env file from template
cp .env.example .env
```

Open `.env` in your text editor and set your key:
```env
GOOGLE_API_KEY=AIzaSy...             # required: from Google AI Studio
DATA_SOURCE=meta_stub                # options: meta_stub | bq_political | meta_live
ADK_ENABLED=true                     # true to route via Google ADK SequentialAgent
```

### 3. Verify Gemini Connectivity & Run Tests

Run the standalone Gemini connectivity check to verify your API key:
```bash
uv run python scripts/test_gemini_connection.py
```

Run the pytest test suite (10 unit & pipeline assembly tests):
```bash
uv run pytest tests/ -v
```

### 4. Boot the Web Application

Start the FastAPI application with `uvicorn`:
```bash
PYTHONPATH=src uv run python -m uvicorn adintel.main:app --reload --port 8000
```

1. Open **[http://localhost:8000](http://localhost:8000)** in your browser.
2. Enter your brand name (e.g. `Warby Parker`) and competitors (e.g. `Ray-Ban, Zenni Optical`).
3. Click **Analyze Competitors**.
4. Check system status and backends live at **[http://localhost:8000/healthz](http://localhost:8000/healthz)**.

---

## Data Source Switching

AdIntel supports three data ingestion backends configured via `DATA_SOURCE` in `.env`:

- **`meta_stub` (Default)**: Deterministic, realistic synthetic competitor ads with varied hooks, CTAs, and delivery windows. No external ad keys needed.
- **`bq_political`**: Queries Google BigQuery public political ads datasets (`bigquery-public-data.google_political_ads.creative_stats`). Requires `gcloud auth application-default login`.
- **`meta_live`**: Connects directly to the Meta Ad Library Graph API v18. Requires `META_ACCESS_TOKEN`.

---

## Project Layout

```
adintel/
├── pyproject.toml
├── .env.example
├── README.md
├── src/adintel/
│   ├── main.py               <- FastAPI entry point & HTMX routes
│   ├── config.py             <- pydantic-settings configuration
│   ├── models.py             <- Ad, Competitor, Pattern, GapItem, GeneratedCreative
│   ├── storage.py            <- LocalJsonStore & FirestoreStore backends
│   ├── clients/
│   │   ├── gemini.py         <- GenAI SDK wrapper (text, vision, structured json, image)
│   │   ├── ads.py            <- Multi-source ad dispatcher
│   │   ├── bq_ads.py         <- BigQuery ads client & mappers
│   │   └── meta_ads.py       <- Meta Ad Library API client
│   ├── agents/
│   │   ├── ingest.py         <- Multi-brand ad ingestion
│   │   ├── longevity.py      <- Pure Python 90-day winner filter
│   │   ├── analyze.py        <- Long-context vision pattern extraction
│   │   ├── gap.py            <- Competitor pattern vs user gap analysis
│   │   ├── create.py         <- Nano Banana concept & PIL fallback card renderer
│   │   ├── report.py         <- Executive summary CMO writer
│   │   ├── orchestrator.py   <- Parallel functional pipeline
│   │   └── adk_pipeline.py   <- Google ADK SequentialAgent pipeline
│   ├── templates/            <- HTMX & Jinja2 HTML templates
│   └── static/               <- Web assets
├── scripts/
│   ├── test_gemini_connection.py
│   └── test_bigquery_connection.py
├── tests/
│   ├── test_smoke.py         <- Pipeline wiring & ADK assembly tests
│   └── test_bq_ads.py        <- BigQuery row mapping tests
└── generated_creatives/      <- Generated PNG creative cards
```

---

## Google Tech Stack

| Component               | Google Tech / Service                                  |
|-------------------------|--------------------------------------------------------|
| Agent Framework         | **Google ADK** (`google.adk.agents.SequentialAgent`)  |
| LLM & Vision Reasoning  | **Gemini 3.5 Flash** (long context + vision)          |
| Multimodal Extraction   | **Gemini 3.5 Flash** (`generate_from_multimodal`)     |
| Image Generation        | **Gemini Flash Image** ("Nano Banana") + PIL fallback |
| Structured Output       | `response_mime_type="application/json"` in GenAI SDK   |
| Public Data Ingestion   | **Google BigQuery** (`google-cloud-bigquery`)          |
| Cloud Storage / State   | **Google Cloud Firestore** (`google-cloud-firestore`)  |
| Compute Target          | **GCP Cloud Run**                                      |

---

## Demo Walkthrough Script (3 minutes)

1. **0:00–0:20** — **Problem**: SMBs burn 80% of Meta ad spend on ineffective creative.
2. **0:20–0:40** — **Input**: Enter brand `Warby Parker` vs competitors `Ray-Ban, Zenni Optical`.
3. **0:40–1:20** — **Pattern Mining**: Watch Gemini analyze 50 competitor ads in parallel, filtering 13 proven winners running 90+ days.
4. **1:20–2:10** — **Gaps**: Review prioritized recommendations (e.g. "Competitors use social-proof question hooks in 70% of winning ads; your ads lack this").
5. **2:10–2:50** — **Creatives**: View ready-to-run concepts with generated image assets and copy rationale.
6. **2:50–3:00** — **Architecture**: Multi-agent design powered by Google ADK & Gemini.
