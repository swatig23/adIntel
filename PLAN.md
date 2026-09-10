# AdIntel - Plan of Attack

> **UPDATE (2026-09-11):** Since the note below, a follow-on commit
> (`776b5cf "refactor 2"`) landed three more features on top of the
> stabilization pass -- see `STATUS.md` "Feature additions" section:
> evidence-backed gap recommendations with real supporting-ad citations,
> a deterministic Creative DNA comparison scorecard, and a `curated_visual`
> data source for a reliable no-network demo fallback. That same commit
> also accidentally committed unresolved git merge-conflict markers into
> `.env.example`, which has since been fixed. Tests are now at 37 passed
> (up from 31).
>
> **UPDATE (2026-09-05):** The morning-kickoff steps below (get API key,
> create BQ sandbox project, set up `.env`) are now **DONE** and
> superseded by the 2026-09-05 stabilization pass -- see `STATUS.md`
> "Stabilization pass" section for the full list of what changed. The app
> now runs on the NEW billed GCP project `project-47457978-49f4-4e71-9a0`
> (migrated off the old `gen-lang-client-0516852331`), the ADK path is
> wired in and is the default (`ADK_ENABLED=true`), Nano Banana UI wording
> is accurate, and the landing page has been redesigned. Kept the original
> kickoff steps below for historical reference / in case `.env` ever needs
> rebuilding from scratch on a new machine.
>
> **What's still open, ranked by priority:**
> 1. Drop a real `GOOGLE_API_KEY` into `.env` on the actual demo
>    machine/network and re-run the full BMW/Audi/AutoZone smoke test --
>    Gemini-dependent stages were not live-verified in the stabilization
>    sandbox (no key available there).
> 2. Verify live BigQuery row-level query access to the new project from
>    an approved network -- the stabilization sandbox hit a VPC Service
>    Controls org policy block; the config itself is confirmed correct.
>    If it stays blocked, `DATA_SOURCE=curated_visual` is a ready fallback.
> 3. If using the curated_visual fallback, populate `demo_ads.json` /
>    `demo_assets/` with real, permissioned competitor ads -- currently
>    near-empty scaffolding.
> 4. Everything in "Afternoon" / "Evening" sections below (second
>    scenario test, demo video, Devpost submission) is still pending.

> **CORRECTED TIMELINE (2026-09-03):** The "8 PM today" deadline below was
> based on an incorrect assumption, not the actual program schedule.
> Official Google Patchamomma 2026 timeline (confirmed via program email):
>
> | Milestone | Date |
> |---|---|
> | Start Build | Aug 15 (past) |
> | First Checkpoint | Aug 20 (past) |
> | **Second Checkpoint (Touchpoint 2)** | **Sep 3 - Google Form due within 48 hrs** |
> | Final Checkpoint | Sep 9 |
> | Lock Submission | Sep 10 (no extensions) |
> | Results | Before Sep 15 |
> | Finale | Sep 24 |
>
> Touchpoint 2 needs a Google Form filled (idea + tech stack, same as
> Touchpoint 1 if unchanged) within 48 hrs. A deployed app link is
> OPTIONAL/bonus at this checkpoint. Real deploy pressure is the Sep 9
> final checkpoint. Work at a sustainable pace across the week, not today.

**Scope locked:** "Cut BQ+MCP+CloudRun, ship safe" (original framing; now
relaxed across the week per corrected timeline above)
**Your available focused time:** spread across the coming week

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

### 5. Create `.env` (2 min) -- DONE as of 2026-09-05, kept for reference
```bash
cd /Users/s0g09hc/Documents/swati/adintel
cp .env.example .env
```
Edit `.env` and set:
```
GOOGLE_API_KEY=AIza...                              # from step 1 -- STILL NEEDED, not set on any machine as of 2026-09-05
GCP_PROJECT_ID=project-47457978-49f4-4e71-9a0       # the new billed project (migrated 2026-09-05)
BQ_KAGGLE_TABLE=project-47457978-49f4-4e71-9a0:commercial_ads.ad_transcripts
DATA_SOURCE=bq_kaggle_transcripts                   # the Kaggle transcripts dataset now lives in the new project
BQ_SKIP_LONGEVITY_FILTER=true                       # this dataset has no delivery-date columns
USE_META_STUB=true                                  # unrelated to DATA_SOURCE, keep true
ADK_ENABLED=true                                    # ADK is now the default orchestration backend
```

> A 6th `DATA_SOURCE=curated_visual` option now also exists for a reliable,
> no-network demo path using a local JSON corpus + local image assets --
> see `DEMO_DATASET.md`. Use it as a fallback if live BigQuery access is
> still blocked on demo day (see "What's still open" item 2 above).

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
# should show 37 passed (as of the 2026-09-11 feature additions)
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
#   "data_source":"bq_kaggle_transcripts" (or "meta_stub" if you skipped BQ)
#   "google_api_key_set":true          <- still needs a real key as of 2026-09-05
#   "gcp_project_id_set":true          <- project-47457978-49f4-4e71-9a0
#   "orchestration_backend":"adk"      <- ADK is the default now (Afternoon section, "Wire the ADK path")
#   "storage_backend":"FirestoreStore" or "LocalJsonStore"
```

### 9. Smoke test the full pipeline (5 min)
- With `DATA_SOURCE=bq_kaggle_transcripts` (the current default): try Brand =
  `BMW`, Competitors = `Audi, AutoZone` -- these are known-present brands in
  the transcripts dataset.
- With `DATA_SOURCE=meta_stub`: try Brand = `Warby Parker`,
  Competitors = `Ray-Ban, Zenni Optical`
- Click "Analyze competitors"
- Wait 30-60 seconds
- Report should render with real (or synthetic) ads, patterns, gaps, and 3 generated ad images (or PIL fallback cards if image quota is 0 -- both are acceptable, see STATUS.md)
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

### 7. Wire the ADK path into FastAPI -- DONE (see STATUS.md "Orchestration" section)

`main.py` now routes through `run_via_adk` by default (`ADK_ENABLED=true` in
`.env`), with the functional `Orchestrator` kept as an instant fallback if
ADK misbehaves mid-demo (`ADK_ENABLED=false`). Confirmed via
`/healthz` -> `"orchestration_backend":"adk"`. Still needs a live run with a
real `GOOGLE_API_KEY` to confirm the Gemini-calling stages produce real
output through the ADK path specifically (see STATUS.md TODO under
Orchestration).

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
- **2:10-2:50** Scroll to the fresh ad creatives. "Generated in 20 seconds, informed by patterns" -- if live Gemini image gen is quota-limited on demo day, say so plainly and show the styled fallback concept cards instead; do not claim Nano Banana generated them if it didn't.
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
1. ~~Wire ADK pipeline into FastAPI~~ -- DONE (2026-09-05 stabilization pass)
2. **Deploy to Cloud Run with live URL** - 1-2 hrs; use `launchpad` sub-agent or `gcloud run deploy`
3. **Add BigQuery for ad history** - largely done via the Kaggle transcripts table migration; remaining work is trend/longitudinal features on top of it
4. **Add MCP Toolbox for BQ** - 2 hrs; lets agents query BQ via tool-calls (huge judge point)

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
2. Nano Banana quota IS exhausted on the free tier (confirmed 0 quota,
   this is not hypothetical) -> `CreateAgent` already auto-generates 3
   styled PIL fallback concept cards (`_draw_fallback_card`) when live
   image gen fails. This is DONE and working -- just be honest about it
   in the UI/demo (see 2026-09-05 stabilization pass): never claim Nano
   Banana generated an image it didn't.
3. If UI polish takes too long -> submit with the functional-orchestrator
   backend + minimal HTMX, skip history/report-view routes
4. If time is critically short -> submit README + code repo + 60-sec video
   walking through the code architecture, skip the polished web demo

**Do not** skip the 3-min video. Every hackathon judge scores off it.
**Do not** skip pushing to GitHub. Judges click the repo link.

---

## Ping me (chat) when

- A real `GOOGLE_API_KEY` is in `.env` on the demo machine -> re-run the
  BMW/Audi/AutoZone smoke test end-to-end and paste the output
- Live BigQuery access is confirmed from an approved network (no more VPC
  Service Controls block) -> paste the query result
- Kickoff step 9 smoke test succeeds -> we celebrate and move to afternoon polish
- Kickoff step 9 smoke test fails -> paste terminal traceback, I fix
- Ready for demo video review -> I can spot-check the script
