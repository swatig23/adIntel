# AdIntel - Troubleshooting (solo mode, no AI assistant needed)

Read this if something breaks on your personal laptop and you're working
without Code Puppy. Find your symptom below.

---

## Setup issues

### "uv: command not found"
You haven't installed `uv` yet.
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# then restart your terminal, or:
source $HOME/.local/bin/env
```

### `uv sync` fails trying to download Python
```
error: Request failed ... python-build-standalone ...
```
Fix: check if you already have Python 3.12+ installed:
```bash
python3 --version
uv python list --only-installed
```
If you see a 3.12.x or 3.13.x already installed, pin to it explicitly:
```bash
uv sync --python 3.12
```
If truly nothing is installed and download fails (rare on personal
network without corporate proxy), install Python via https://python.org
or `brew install python@3.12`, then retry `uv sync --python 3.12`.

### `.python-version` says 3.11 but you only have 3.12
This project was originally pinned to 3.11 then relaxed to 3.12 (see
`pyproject.toml` `requires-python = ">=3.12"`). If `.python-version`
still says `3.11`, just overwrite it:
```bash
echo "3.12" > .python-version
uv sync
```

### Tests won't run: "ModuleNotFoundError: No module named 'adintel'"
You're not using the venv's Python. Always run either:
```bash
uv run pytest tests/
# OR
.venv/bin/python -m pytest tests/
```
Never plain `python -m pytest` or `pytest` (that uses your system Python).

---

## Gemini / auth issues

The app supports two auth modes. Check which you are using:

```bash
grep GOOGLE_API_KEY .env   # Option A: should be non-empty
grep GCP_PROJECT_ID .env   # Option B: should be non-empty, GOOGLE_API_KEY blank
```

---

### Option A (AI Studio) — `"GOOGLE_API_KEY is not set"` error
- Check `.env` exists: `ls -la .env` (note the leading dot)
- Confirm it has a real key: `grep GOOGLE_API_KEY .env`
  Should show `GOOGLE_API_KEY=AIza...` not an empty value
- Get a key at https://aistudio.google.com/apikey if you don't have one

### Option A — `403 PERMISSION_DENIED` or `API key not valid`
- Key might be malformed (extra spaces/quotes). The line must look exactly like:
  `GOOGLE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`
  (no quotes, no trailing spaces)
- Regenerate the key at https://aistudio.google.com/apikey

### Option B (Vertex AI) — `"No Gemini auth configured"` error
The app couldn't find either a valid API key or GCP credentials. Fix:
```bash
# 1. Confirm your project ID is set:
grep GCP_PROJECT_ID .env           # should be non-empty

# 2. Confirm ADC is active:
gcloud auth application-default print-access-token   # must return a token

# 3. If not, log in:
gcloud auth application-default login

# 4. Confirm Vertex AI API is enabled on the project:
gcloud services enable aiplatform.googleapis.com
```

### Option B (Vertex AI) — `403 PERMISSION_DENIED` on Vertex AI call
- Your ADC account doesn't have `Vertex AI User` role on the project.
  Grant it in IAM:
  ```bash
  gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:you@example.com" \
    --role="roles/aiplatform.user"
  ```
- Or via Cloud Console: IAM → your account → Add role → "Vertex AI User"

### Option B (Vertex AI) — `404 model not found` for image model
- Confirm `GEMINI_IMAGE_MODEL=gemini-2.5-flash-image` in `.env`
- Confirm `GCP_LOCATION=global` — `gemini-2.5-flash-image` requires `global`, not a regional endpoint
- Check model availability: https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versioning

### `429 RESOURCE_EXHAUSTED` (rate limit)
- Free-tier / quota limits hit. Wait 60 seconds and retry.
- If it keeps happening during a full pipeline run (~15 Gemini calls),
  space out test runs by a minute or two.

### `SSL: CERTIFICATE_VERIFY_FAILED`
Should not happen on a personal laptop without a corporate proxy.
- Confirm you're not on a corporate VPN
- Try: `.venv/bin/python -m pip install --upgrade certifi`
- Check system date/time is correct (wrong clocks break TLS)

### Gemini call hangs / times out
- Check internet connection
- For Vertex AI, confirm the region in `GCP_LOCATION` is correct
- Test with a smaller isolated call before running the full pipeline

---

## Pipeline / application issues

### `AnalyzeAgent` or `GapAgent` returns empty patterns/gaps
This usually means Gemini returned malformed JSON that our parser
couldn't handle. Check the terminal logs (loguru output) right above
the error — it prints the raw response's first 400 characters. Common
causes:
- Gemini wrapped the JSON in markdown fences despite instructions
  (our code already strips ```json fences, but rare edge cases slip
  through)
- Gemini added a sentence of preamble before the JSON

Workaround if this blocks your demo: reduce ambition, re-run the
analysis (LLM outputs vary run to run), or manually inspect
`src/adintel/agents/analyze.py` `_parse_patterns()` and loosen the
regex if needed.

### "Generate AI Visual" button shows an error / image not replaced
1. **"No saved report"** — the report failed to persist (check server logs for
   storage errors). Re-run the analysis; if Firestore is misconfigured,
   add `GCP_PROJECT_ID` to `.env` or check Firestore init logs.
2. **"Image generation failed. Check Vertex AI access, billing, or model availability."** — Vertex AI
   auth isn't configured correctly, billing isn't enabled on the project, or the model is
   unavailable. Switch to Option B (Vertex AI) — see auth section above.
3. **"disabled (IMAGE_GENERATION_ENABLED=false)"** — the kill switch is active.
   Set `IMAGE_GENERATION_ENABLED=true` in `.env` and restart.
4. **"did not return any image bytes"** — the model returned no image, often
   a safety-filter rejection. Try a different competitor brand or a more
   neutral `industry_hint`, then click Generate again.
5. **Confirm the model name:** `GEMINI_IMAGE_MODEL=gemini-2.5-flash-image`
   (no `-preview` suffix). Typos here fail silently at client init.

### FastAPI app won't start: "Address already in use"
Something is already running on port 8000.
```bash
lsof -ti:8000 | xargs kill -9
# then retry
.venv/bin/python -m uvicorn adintel.main:app --reload --port 8000
```

### `/healthz` shows `"storage_backend":"LocalJsonStore"` but I wanted Firestore
- Means `GCP_PROJECT_ID` is blank in `.env`, OR Firestore init failed
  silently (check terminal logs for "[storage] Firestore init failed").
- LocalJsonStore is a perfectly valid fallback — it still satisfies
  "at least one Cloud Service" is NOT technically true (it's local
  disk). If you need the Cloud Service checkbox, Firestore MUST work.
  Debug by running this in isolation:
  ```bash
  .venv/bin/python -c "
  from dotenv import load_dotenv; load_dotenv()
  from adintel.storage import get_store
  print(type(get_store()).__name__)
  "
  ```
  If it prints `LocalJsonStore`, check the printed warning above it.

### Before flipping DATA_SOURCE=bq_political, run the pre-flight check
Don't set `DATA_SOURCE=bq_political` blind. Run this first:
```bash
.venv/bin/python scripts/test_bigquery_connection.py
```
It checks, in order: config is set, auth works, the LIVE table schema
matches what the code expects (this was written from docs, never
verified live -- schemas drift), and finally runs one real sample
query. Fixes exactly what's wrong instead of guessing from a raw
BigQuery stack trace.

### BigQuery query fails: "403 Access Denied" or "billing not enabled"
- BQ Sandbox mode has limits on some operations. If this happens:
  1. Confirm `gcloud auth application-default login` was run
  2. Confirm `GCP_PROJECT_ID` in `.env` matches your actual project ID
     (check https://console.cloud.google.com/bigquery top-left dropdown)
  3. As a fallback, set `DATA_SOURCE=meta_stub` in `.env` and restart —
     this unblocks your demo immediately; debug BQ access separately
     later since it's not on the critical path for a working demo.

### BigQuery query fails: "column not found" (e.g. `spend_range_min_usd`)
The public dataset schema may have changed since this code was written.
Run this to see actual column names:
```bash
# Requires bq CLI (comes with gcloud) or use the BigQuery web console:
# https://console.cloud.google.com/bigquery
# Paste this query:
SELECT column_name, data_type
FROM `bigquery-public-data.google_political_ads.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'creative_stats'
ORDER BY ordinal_position;
```
Then edit `_POLITICAL_COLUMNS` list and the row-mapping function in
`src/adintel/clients/bq_ads.py` to match. There's a TODO comment there
pointing to this exact query.

---

## When all else fails: fallback ladder

Use this priority order to guarantee SOMETHING works for your demo:

1. **Full pipeline with BigQuery real data** (best) — `DATA_SOURCE=bq_political`
2. **Full pipeline with synthetic stub data** — `DATA_SOURCE=meta_stub`
   (still 100% functional, just not "real" data — acceptable per hackathon rules)
3. **Partial pipeline** — if creative generation is flaky,
   set `generate_creatives=false` in the request form and demo just the
   pattern-analysis + gap-report parts
4. **Static screenshots** — if the live app breaks right before deadline,
   screenshot a previous successful run (check `data/analyses/*.json`
   for past outputs) and narrate over screenshots in your video

Never let a broken live demo become your final submission story — a
video walkthrough of a working PAST run beats a broken LIVE attempt.

---

## Quick reference: full command sequence from clean checkout

```bash
cd /path/to/adintel
uv sync --python 3.12
cp .env.example .env
```

**If using AI Studio (Option A):**
```bash
# edit .env: set GOOGLE_API_KEY=AIza...
```

**If using Vertex AI (Option B — recommended):**
```bash
# edit .env: set GCP_PROJECT_ID=your-project-id, leave GOOGLE_API_KEY blank
gcloud auth application-default login
gcloud services enable aiplatform.googleapis.com
```

**Then run:**
```bash
.venv/bin/python -m pytest tests/ -v
.venv/bin/python -m uvicorn adintel.main:app --reload --port 8000
# open http://localhost:8000
```
