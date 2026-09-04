"""FastAPI entry point for AdIntel.

Endpoints:
* GET  /                    → landing form
* POST /analyze             → runs the pipeline; returns HTMX report fragment
* GET  /creatives/{name}    → serves generated ad images
* GET  /healthz             → liveness

Run locally:
    uv run uvicorn adintel.main:app --reload --port 8000
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

# Load .env before importing anything that reads settings
load_dotenv()

from .agents.adk_pipeline import run_via_adk  # noqa: E402
from .agents.orchestrator import Orchestrator  # noqa: E402
from .config import get_settings  # noqa: E402
from .models import AnalysisRequest  # noqa: E402
from .storage import get_store  # noqa: E402

# ────────────────────────────────────────────────────────────────
# Setup
# ────────────────────────────────────────────────────────────────
settings = get_settings()

logger.remove()
logger.add(sys.stderr, level=settings.log_level, colorize=True)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
CREATIVE_DIR = Path("generated_creatives").resolve()
CREATIVE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AdIntel", version="0.1.0")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

orchestrator = Orchestrator(creative_output_dir=CREATIVE_DIR)
store = get_store()


async def run_pipeline(req: AnalysisRequest):
    """Runs the AdIntel pipeline via ADK's SequentialAgent by default, or
    the plain functional Orchestrator if ADK_ENABLED=false in .env. Both
    paths execute the identical six agents and return the same shape --
    this is purely a routing decision, useful as an instant fallback if
    ADK ever misbehaves mid-demo without touching any agent code.
    """
    if settings.adk_enabled:
        logger.info('[main] routing through ADK SequentialAgent')
        return await run_via_adk(req, creative_output_dir=CREATIVE_DIR)
    logger.info('[main] routing through functional Orchestrator')
    return await orchestrator.run(req)


# ────────────────────────────────────────────────────────────────
# Routes
# ────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"using_stub": settings.use_meta_stub},
    )


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    user_brand: str = Form(...),
    competitors: str = Form(...),
    industry_hint: str = Form(""),
    generate_creatives: str = Form("off"),
):
    competitor_list = [c.strip() for c in competitors.split(",") if c.strip()]
    if not competitor_list:
        raise HTTPException(400, "At least one competitor is required")

    req = AnalysisRequest(
        user_brand=user_brand.strip(),
        competitors=competitor_list[:10],
        industry_hint=industry_hint.strip() or None,
        generate_creatives=(generate_creatives.lower() in ("on", "true", "yes")),
    )

    try:
        report = await run_pipeline(req)
    except Exception as e:  # noqa: BLE001
        logger.exception("Pipeline failed")
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"error": str(e)},
            status_code=500,
        )

    # Persist for history / sharing
    try:
        report_id = store.save(report)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Could not persist report: {e}")
        report_id = None

    return templates.TemplateResponse(
        request=request,
        name="report.html",
        context={"report": report, "report_id": report_id},
    )


@app.get("/creatives/{filename}")
async def serve_creative(filename: str):
    # Prevent path traversal
    safe = Path(filename).name
    path = CREATIVE_DIR / safe
    if not path.exists():
        raise HTTPException(404, f"Creative not found: {safe}")
    return FileResponse(path, media_type="image/png")


@app.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "data_source": settings.data_source,
        "using_stub": settings.use_meta_stub,
        "orchestration_backend": "adk" if settings.adk_enabled else "functional",
        "storage_backend": type(store).__name__,
        "gcp_project_id_set": bool(settings.gcp_project_id),
        "google_api_key_set": bool(settings.google_api_key),
    }


@app.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    rows = store.list_recent(limit=25)
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"rows": rows},
    )


@app.get("/report/{report_id}", response_class=HTMLResponse)
async def view_report(request: Request, report_id: str):
    report = store.load(report_id)
    if not report:
        raise HTTPException(404, f"Report {report_id} not found")
    return templates.TemplateResponse(
        request=request,
        name="report_page.html",
        context={"report": report, "report_id": report_id},
    )
