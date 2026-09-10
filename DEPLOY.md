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
`--source` does it all in one command.

**Option A — AI Studio API key auth:**
```bash
cd /path/to/adintel

gcloud run deploy adintel \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_API_KEY=YOUR_AI_STUDIO_KEY,DATA_SOURCE=meta_stub,USE_META_STUB=true,GCP_PROJECT_ID=YOUR_PROJECT_ID,GCP_LOCATION=us-central1"
```

**Option B — Vertex AI auth (recommended; no API key needed):**
```bash
cd /path/to/adintel

gcloud run deploy adintel \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "DATA_SOURCE=meta_stub,USE_META_STUB=true,GCP_PROJECT_ID=YOUR_PROJECT_ID,GCP_LOCATION=us-central1,IMAGE_GENERATION_ENABLED=true"
```
With Option B, leave `GOOGLE_API_KEY` out of `--set-env-vars` entirely.
The app automatically uses the Cloud Run service account's credentials
for all Gemini and Vertex AI calls (see step 2b below for IAM setup).

Notes:
- `--allow-unauthenticated` = public URL, anyone with the link can open it
  (fine for a hackathon demo; judges need to click it without auth)
- Start with `DATA_SOURCE=meta_stub` for the FIRST deploy - guarantees it
  works without depending on BigQuery auth inside the container. Switch
  to `bq_kaggle_transcripts` in a second deploy once the basic version is proven live.
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

## Step 2b: Grant the Cloud Run service account the right IAM roles

Cloud Run containers don't use your local `gcloud auth application-default login`
credentials. They run as a GCP service account. For Vertex AI and BigQuery to
work inside the deployed container, grant that service account the correct roles.

```bash
# Find the default compute service account (used by Cloud Run unless you
# created a custom one):
gcloud iam service-accounts list
# It looks like: 123456789-compute@developer.gserviceaccount.com

# Replace YOUR_PROJECT_ID and YOUR_PROJECT_NUMBER below:

# Vertex AI (required for on-demand image generation):
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# BigQuery (required for DATA_SOURCE=bq_* modes):
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
```

If you want to skip IAM setup for the first deploy, use `DATA_SOURCE=meta_stub`
and `IMAGE_GENERATION_ENABLED=false` — that gets you a working live demo without
needing any service account roles. Add roles and redeploy once the baseline works.

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
