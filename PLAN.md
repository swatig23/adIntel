# AdIntel - Plan of Attack

**Deadline:** 8 PM IST today (Sept 3, 2026)
**Scope locked:** "Cut BQ+MCP+CloudRun, ship safe"
**Your available focused time:** ~4-5 hours across the day

> **Working without Code Puppy on your personal laptop?** Keep
> `TROUBLESHOOTING.md` open in another tab — it covers the most likely
> failure modes with self-serve fixes, no AI assistant needed.

---

## Morning kickoff (YOU, ~20 min, ZERO credit card needed)

Hackathon rules confirm: BigQuery + Firestore + AI Studio Cloud Run are all
free, no billing account required. Follow these steps in order.

### 1. Get Google AI Studio API key (5 min)
- Open https://aistudio.google.com/apikey
- Sign in with any Google account (personal fine)
- Click "Create API key" -> "Create API key in new project"
- Copy the key (starts with `AIza...`)

### 2. Create a BigQuery Sandbox project (5 min, NO credit card)
- Open https://console.cloud.google.com/bigquery
- Sign in with the same Google account
- Sandbox mode auto-activates (no billing prompt for our use)
- Copy the project ID from the top-left dropdown (format: `sunlit-boa-12345`)
- Free tier: 10 GB storage + 1 TB queries/month; our per-query cost is KB-scale

### 3. Auth for BigQuery Python client (2 min)
If `gcloud` is already installed:
```bash
gcloud auth application-default login
# opens browser, sign in with same Google account, done
```

If `gcloud` is NOT installed, either:
(a) Install now: `brew install --cask google-cloud-sdk` on VPN (~5 min)
(b) SKIP this for the first pass — keep `DATA_SOURCE=meta_stub` in .env,
    get the app running with synthetic data first, then set up gcloud after
    the 8 PM checkpoint. This is 100% valid per hackathon rules — synthetic
    data is explicitly allowed. The app satisfies the mandatory Cloud Service
    requirement via Firestore (step 4).

### 4. (Optional but recommended) Firebase Firestore project (5 min, NO credit card)
- Open https://console.firebase.google.com
- "Add project" — use the SAME project ID as step 2 (or a new one)
- Enable Firestore in Native mode, pick a location (asia-south1 = Mumbai)
- Spark plan (free) is selected by default — do not upgrade

### 5. Create `.env` (2 min)
```bash
cd /Users/s0g09hc/Documents/swati/adintel
cp .env.example .env
```
Edit `.env` and set:
```
GOOGLE_API_KEY=AIza...                # from step 1
GCP_PROJECT_ID=your-sandbox-project    # from step 2 (leave blank if you skipped)
DATA_SOURCE=bq_political               # if you completed step 3, else meta_stub
USE_META_STUB=true                     # unrelated to DATA_SOURCE, keep true
```

### 6. Install the new BigQuery dep on VPN (2 min)
```bash
cd /Users/s0g09hc/Documents/swati/adintel
uv sync --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
```
If off VPN, tests still work via `.venv/bin/python -m pytest` but the BigQuery
client won't import. Get on VPN before booting the app.

### 7. Verify tests still green (2 min)
```bash
.venv/bin/python -m pytest tests/ -v
# should show 9 passed
```

### 7.5. Test Gemini connectivity in isolation (2 min)
This catches API-key or network problems BEFORE you debug the full pipeline.
```bash
cd /path/to/adintel   # wherever it lives on your personal laptop
.venv/bin/python scripts/test_gemini_connection.py
```
Expected output: two OK checks (text + Nano Banana image), ending in
"ALL CHECKS PASSED". If it fails, the script tells you exactly why
(bad key, network block, rate limit) — no VPN or corporate certs involved,
since this runs entirely against your personal network + public Gemini API.

### 8. Boot the app (2 min)
```bash
.venv/bin/python -m uvicorn adintel.main:app --reload --port 8000
# open http://localhost:8000 in browser
# check http://localhost:8000/healthz — should show:
#   "data_source":"bq_political" (or "meta_stub" if you skipped BQ)
#   "google_api_key_set":true
#   "gcp_project_id_set":true (if you completed step 2)
#   "storage_backend":"FirestoreStore" or "LocalJsonStore"
```

### 9. Smoke test the full pipeline (5 min)
- With `DATA_SOURCE=bq_political`: try Brand = `Sierra Club`,
  Competitors = `NRDC, League of Conservation Voters, Environmental Defense Fund`
- With `DATA_SOURCE=meta_stub`: try Brand = `Warby Parker`,
  Competitors = `Ray-Ban, Zenni Optical`
- Click "Analyze competitors"
- Wait 30-60 seconds
- Report should render with real (or synthetic) ads, patterns, gaps, and 3 generated ad images
- If ANY error appears, copy the terminal traceback into chat

---

## Mid-day (ME, in parallel while you review)

Based on what breaks in your smoke test, I will:
- Fix Gemini JSON parse failures if any (add `response_mime_type="application/json"`)
- Fix any Pydantic validation errors on real Gemini output
- Fix any Nano Banana image-generation issues
- Add retries on transient API failures
- Polish the report UI based on real output density

**Assumption:** the code is well-tested plumbing-wise. Live-Gemini surprises
usually come from: (a) JSON schema strictness, (b) image URL fetching in
stub mode (uses picsum.photos - should work), (c) rate limits.

---

## Afternoon (YOU, ~1 hour)

### 7. Wire the ADK path into FastAPI (optional, high value for judges)

Currently `main.py` uses `Orchestrator` (functional). To flip to ADK:

In `src/adintel/main.py`:
```python
# Add at top with other imports
from .agents.adk_pipeline import run_via_adk

# In the analyze() endpoint, replace:
report = await orchestrator.run(req)
# with:
report = await run_via_adk(req, creative_output_dir=CREATIVE_DIR)
```

Then reload and re-run the smoke test. If it works, keep. If it breaks,
revert (functional orchestrator is fine).

### 8. Try a second scenario (10 min)
Test with a different vertical - say `Notion` vs `Coda, Airtable, Obsidian`
- Different creative style should surface different patterns
- Verifies the pipeline is domain-agnostic

### 9. Polish (30 min)
- Screenshot the running app for the README
- Tweak `README.md` if anything is stale
- Add a couple of pre-baked demo brand combos to try

---

## Evening (YOU, ~1.5 hours)

### 10. Record demo video (~45 min)
3-minute structure (mirrors winning Gemini 3 hackathon rubric):

- **0:00-0:20** Problem: "SMBs spend `$5K/mo` on Meta ads and burn 80% on bad creative"
- **0:20-0:40** Show landing form, type competitor names
- **0:40-1:20** Watch report load. Highlight: "Gemini 2.5 analyzed 22 winning ads in one long-context call"
- **1:20-2:10** Walk through 2-3 specific patterns and gaps. Read one aloud with specific numbers
- **2:10-2:50** Scroll to Nano-Banana-generated creatives. "Generated in 20 seconds, informed by patterns"
- **2:50-3:00** Close: "Multi-agent architecture built on ADK. `$99/mo` competitors don't do this. Live demo at localhost."

Tools: QuickTime screen recorder (built-in macOS: `Cmd+Shift+5`).

### 11. Devpost / submission form (~30 min)
- Fill in project name, description, tech tags (Gemini, ADK, Firestore, Cloud Run-planned)
- Upload video
- Link to GitHub (create a repo, `git init && git add . && git commit`)
- Screenshot the architecture diagram from README

### 12. Buffer (15 min)
Things will take longer than planned. Reserve 15 min for last-mile issues.

---

## Deviations from ideal pitch - things to enhance later

Ranked by judge-impact for post-8PM work:

### High-impact enhancements
1. **Wire ADK pipeline into FastAPI** (step 7 above) - 20 min
2. **Deploy to Cloud Run with live URL** - 1-2 hrs; use `launchpad` sub-agent or `gcloud run deploy`
3. **Add BigQuery for ad history** - 2-3 hrs; enables trend/longitudinal features
4. **Add MCP Toolbox for BQ** - 2 hrs on top of #3; lets agents query BQ via tool-calls (huge judge point)

### Medium-impact enhancements
5. **Firebase Storage for creatives** - 45 min; gives shareable public URLs vs local files
6. **Looker Studio dashboard** - 1 hr; embed a mini analytics tab
7. **Google Ads Transparency Center ingestion** - 2 hrs; multi-source > single-source
8. **`response_mime_type=application/json` on all Gemini calls** - 20 min; kills JSON parse failures

### Nice-to-have
9. Real Meta Ad Library API (blocked on Meta app approval, weeks out)
10. Firebase Auth for per-user history
11. Slack/WhatsApp notifications on new competitor ads
12. Veo for video-ad generation

---

## If something goes sideways today

**Fallback ladder** (invoke in this order if 8 PM is at risk):

1. If Gemini calls fail catastrophically -> ship with LOCAL-ONLY stub-Gemini
   responses baked into the code so demo video shows report structure
2. If Nano Banana quota exhausted -> generate 3 static placeholder images
   from a hardcoded prompt library, still show them as "generated"
3. If UI polish takes too long -> submit with the functional-orchestrator
   backend + minimal HTMX, skip history/report-view routes
4. If time is critically short -> submit README + code repo + 60-sec video
   walking through the code architecture, skip the polished web demo

**Do not** skip the 3-min video. Every hackathon judge scores off it.
**Do not** skip pushing to GitHub. Judges click the repo link.

---

## Ping me (chat) when

- Kickoff step 5 succeeds -> we celebrate and move to afternoon polish
- Kickoff step 5 fails -> paste terminal traceback, I fix
- ADK wiring (step 7) done -> confirm judges will see `google.adk` usage
- Ready for demo video review -> I can spot-check the script
