# AdIntel - Deploy to Cloud Run (personal laptop, no Code Puppy needed)

Same free path GlowMatch used: AI Studio -> Cloud Run. This gets you a
public URL, which matters more right now than any further optimization.

---

## Fastest path: AI Studio's built-in Cloud Run deploy button

1. Open https://aistudio.google.com
2. If your app was built/tracked in AI Studio already, look for a
   "Deploy" or "Publish" button in the top bar. AI Studio gives you
   2 free Cloud Run deployments (per the hackathon rules doc).
3. If AI Studio doesn't recognize this as one of its projects (likely,
   since we built AdIntel outside AI Studio's UI), use the manual
   `gcloud` path below instead - same free Cloud Run tier applies either way.

---

## Manual path via gcloud CLI (works regardless of AI Studio linkage)

### 0. Prerequisites check
```bash
gcloud --version
# if missing: brew install --cask google-cloud-sdk
gcloud auth login
gcloud config set project YOUR_PROJECT_ID   # same project ID from .env
```

### 1. Enable Cloud Run + Artifact Registry (one-time, free)
```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
```

### 2. Deploy directly from source (gcloud builds the container for you)
No need to build/push Docker images by hand - `gcloud run deploy` with
`--source` does it all in one command:

```bash
cd /path/to/adintel

gcloud run deploy adintel \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_API_KEY=YOUR_KEY_HERE,DATA_SOURCE=meta_stub,USE_META_STUB=true,GCP_PROJECT_ID=YOUR_PROJECT_ID"
```

Notes:
- `--allow-unauthenticated` = public URL, anyone with the link can open it
  (fine for a hackathon demo; judges need to click it without auth)
- Start with `DATA_SOURCE=meta_stub` for the FIRST deploy - guarantees it
  works without depending on BigQuery auth inside the container. Switch
  to `bq_political` in a second deploy once the basic version is proven live.
- Takes 3-5 minutes the first time (builds container, pushes, deploys)
- Output ends with a URL like `https://adintel-xxxxx-uc.a.run.app` - THAT
  is your submission link

### 3. If it fails on the Dockerfile / build step
A `Dockerfile` is already included in this repo (project root). If
`gcloud run deploy --source .` has trouble auto-detecting it, force it:
```bash
gcloud run deploy adintel --source . --region us-central1 --allow-unauthenticated
```
(gcloud auto-detects the Dockerfile in the current directory - no extra flag needed)

### 4. Verify it's live
```bash
curl https://adintel-xxxxx-uc.a.run.app/healthz
```
Should return JSON with `"status":"ok"`.

Then open the URL in a browser and run one full analysis end-to-end,
exactly like your localhost test.

---

## If BigQuery auth fails inside the deployed container

Cloud Run containers don't automatically have your local
`gcloud auth application-default login` credentials. Two options:

**Option A (fastest): stay on meta_stub for the live demo**
Just don't set `DATA_SOURCE=bq_political` in the deployed environment
variables. Ship with synthetic data live, mention in your demo video
that BigQuery integration is proven locally and code-complete (it is -
see STATUS.md). This is a perfectly valid scope cut under time pressure.

**Option B: grant the Cloud Run service account BigQuery access**
```bash
# Find the default compute service account:
gcloud iam service-accounts list

# Grant it BigQuery Data Viewer + Job User roles:
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
```
Then redeploy with `DATA_SOURCE=bq_political` in env vars.

Do Option A first. Do Option B only if you have time left after a
working live demo exists.

---

## After first successful deploy: redeploying is fast

Once the container builds once, iterating is quick:
```bash
gcloud run deploy adintel --source . --region us-central1
```
(flags like `--allow-unauthenticated` and env vars persist from the
first deploy unless you change them)

---

## Fallback if gcloud deploy is fighting you and time is short

Per the hackathon rules, render.com or netlify are acceptable "worst
case only" fallbacks. Render's free tier supports Docker deploys
directly from a GitHub repo (which you already have):

1. https://render.com -> New -> Web Service
2. Connect your GitHub repo
3. Render auto-detects the `Dockerfile`
4. Add the same environment variables as above in Render's dashboard
5. Deploy - gives you a `https://adintel.onrender.com`-style URL

This is genuinely a fine fallback - a working Render URL beats a
broken/absent Cloud Run deploy every time.
