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
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

# Load .env before importing anything that reads settings
load_dotenv()

from .agents.adk_pipeline import run_via_adk  # noqa: E402
from .agents.orchestrator import Orchestrator  # noqa: E402
from .clients.curated_visual import asset_directory  # noqa: E402
from .clients.gemini import generate_image  # noqa: E402
from .config import get_settings  # noqa: E402
from .markdown_lite import render_report_markdown  # noqa: E402
from .models import AnalysisReport, AnalysisRequest  # noqa: E402
from .report_dashboard import (  # noqa: E402
    competitor_chart_data,
    competitive_scorecard,
    data_quality_summary,
    extract_headline,
    extract_strategy_name,
    extract_summary_section,
    gap_coverage_chart_data,
    gap_evidence_cards,
    pattern_chart_data,
    top_patterns,
)
from .storage import get_store  # noqa: E402
from .text_presentation import sentence_preview, truncate_words  # noqa: E402

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
templates.env.filters["report_md"] = render_report_markdown
templates.env.filters["sentence_preview"] = sentence_preview
templates.env.filters["truncate_words"] = truncate_words
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


def _friendly_error_context(exc: Exception) -> dict:
    """Maps an internal exception to a short, user-safe message + a plain
    English hint on what to try next. Never leaks tracebacks, file paths,
    or raw API error bodies to the browser -- those stay in server logs
    (see logger.exception call at the call site). Add new categories here
    as new failure modes surface; keep the fallback branch last.
    """
    text = str(exc)

    if "RESOURCE_EXHAUSTED" in text or "429" in text:
        return {
            "title": "Gemini quota reached",
            "message": (
                "We've hit the free-tier request limit for Gemini right now. "
                "This resets daily -- try again shortly, or ask the team to "
                "enable billing for higher limits."
            ),
        }
    if "credentials" in text.lower() or "GOOGLE_API_KEY" in text:
        return {
            "title": "AI service not configured",
            "message": (
                "The server is missing a valid Gemini API key. This is a "
                "configuration issue, not something you can fix from here."
            ),
        }
    if "BigQuery" in text or "bigquery" in text.lower() or "gcp" in text.lower():
        return {
            "title": "Couldn't reach the ad data source",
            "message": (
                "We had trouble querying the competitor ad database. "
                "Please try again in a moment."
            ),
        }
    return {
        "title": "Something went wrong",
        "message": (
            "We couldn't finish this analysis. Please try again, and double "
            "check the brand names are spelled correctly."
        ),
    }


def _report_context(report: AnalysisReport, report_id: str | None) -> dict:
    """Shared template context for both the fresh /analyze response and
    the persisted /report/{id} view -- keeps chart-data wiring in one
    place instead of duplicated across two routes.
    """
    return {
        "report": report,
        "report_id": report_id,
        "headline": extract_headline(report.executive_summary),
        "strategy_name": extract_strategy_name(report.executive_summary),
        "whats_working": extract_summary_section(report.executive_summary, "What's working for competitors"),
        "top_moves": extract_summary_section(report.executive_summary, "Your top 3 moves this week"),
        "what_not_to_do": extract_summary_section(report.executive_summary, "What NOT to do"),
        "opportunity_evidence": top_patterns(report, n=3),
        "pattern_chart": pattern_chart_data(report),
        "gap_chart": gap_coverage_chart_data(report),
        "gap_evidence": gap_evidence_cards(report),
        "competitor_chart": competitor_chart_data(report),
        "scorecard": competitive_scorecard(report),
        "data_quality": data_quality_summary(report),
        # When the active data source has no delivery-date signal (see
        # BQ_SKIP_LONGEVITY_FILTER), "winner" isn't a measured outcome --
        # every ad passes through untouched. The UI must say so plainly
        # instead of implying a performance judgment the data can't back.
        "winners_are_proxy_only": settings.bq_skip_longevity_filter,
    }


# ────────────────────────────────────────────────────────────────
# Routes
# ────────────────────────────────────────────────────────────────


def _live_status_label(using_stub: bool, data_source: str) -> str:
    """Short, accurate header badge text for the landing page. Never
    claims a backend that isn't actually active."""
    if using_stub:
        return "DEMO MODE \u00b7 Stubbed Data"
    if data_source.startswith("bq_"):
        return "LIVE DATA \u00b7 BigQuery"
    if data_source == "meta_live":
        return "LIVE DATA \u00b7 Meta Ad Library"
    return f"LIVE DATA \u00b7 {data_source}"


def _latest_metrics() -> dict | None:
    """Best-effort metrics strip for the landing page, pulled from the
    most recently persisted analysis (if any). Returns None when no
    analysis has been run yet -- the template falls back to neutral
    placeholders ("--") instead of fabricating numbers. Any storage
    hiccup here must never break the landing page, so failures are
    swallowed and logged, same policy as the /analyze persistence path.
    """
    try:
        recent = store.list_recent(limit=1)
        if not recent:
            return None
        report = store.load(recent[0]["id"])
        if not report:
            return None
        return {
            "ads": sum(len(c.ads) for c in report.competitors),
            "patterns": len(report.patterns),
            "gaps": sum(1 for g in report.gaps if not g.user_has),
            "creatives": len(report.generated_creatives),
        }
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[main] could not load landing-page metrics: {e}")
        return None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    using_stub = settings.data_source == "meta_stub" and settings.use_meta_stub
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            # This banner used to always check settings.use_meta_stub, a
            # flag that only matters when data_source=="meta_stub" -- so
            # BigQuery/Kaggle-backed runs incorrectly showed "DEMO MODE"
            # forever. Gate it on the actual active data_source instead.
            "using_stub": using_stub,
            "data_source": settings.data_source,
            "status_label": _live_status_label(using_stub, settings.data_source),
            "metrics": _latest_metrics(),
        },
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
        # Full exception (with traceback) always goes to server logs only --
        # raw internals (file paths, API error bodies, prompts) must never
        # reach the browser. The user gets a short, actionable message.
        logger.exception("Pipeline failed")
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context=_friendly_error_context(e),
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
        context=_report_context(report, report_id),
    )


@app.get("/creatives/{filename}")
async def serve_creative(filename: str):
    # Prevent path traversal
    safe = Path(filename).name
    path = CREATIVE_DIR / safe
    if not path.exists():
        raise HTTPException(404, f"Creative not found: {safe}")
    return FileResponse(path, media_type="image/png")


@app.post("/generate-creative")
async def generate_creative_image(
    creative_index: int = Form(...),
    report_id: str = Form(...),
):
    """On-demand Gemini image generation for a single creative card.

    Intentionally separated from /analyze -- the pipeline never calls this.
    Requires IMAGE_GENERATION_ENABLED=true (default) and a valid GOOGLE_API_KEY
    with image-generation quota. Each call covers exactly one creative; the
    other creatives are never touched.
    """
    if not settings.image_generation_enabled:
        return JSONResponse(
            {
                "status": "disabled",
                "message": "Image generation is currently disabled (IMAGE_GENERATION_ENABLED=false).",
            },
            status_code=503,
        )

    if not report_id or report_id == "None":
        return JSONResponse(
            {"status": "error", "message": "No saved report found for this analysis."},
            status_code=400,
        )

    report = store.load(report_id)
    if not report:
        return JSONResponse(
            {"status": "error", "message": "Report not found or has expired."},
            status_code=404,
        )

    idx = creative_index - 1  # convert to 0-based
    if idx < 0 or idx >= len(report.generated_creatives):
        return JSONResponse(
            {"status": "error", "message": "Creative index out of range."},
            status_code=400,
        )

    creative = report.generated_creatives[idx]
    brand = report.request.user_brand

    # Build a clean advertising prompt.  Copy and headlines live in the UI
    # card, not inside the generated image -- the image must be text-free.
    prompt = (
        f"A clean advertising visual for {brand}. "
        f"{creative.hook}. "
        f"Professional advertising photography, studio quality, "
        f"clean composition, aspirational mood, commercial product photography. "
        f"Absolutely no text, no typography, no headlines, no captions, "
        f"no logos, no watermarks, no words of any kind in the image."
    )

    brand_slug = brand.lower().replace(" ", "_").replace("-", "_")
    out_filename = f"{brand_slug}_creative_{creative_index}_gemini.png"
    out_path = CREATIVE_DIR / out_filename

    try:
        await generate_image(prompt, out_path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[generate-creative] Vertex AI image generation failed: {e}")
        # PIL fallback for on-demand failure only — image is labelled
        # "Local fallback — not generated by Gemini" inside the PNG itself.
        try:
            from .agents.create import CreateAgent
            concept = {"hook": creative.hook, "body_copy": creative.body_copy, "cta": creative.cta}
            CreateAgent._draw_fallback_card(brand, creative_index - 1, concept, out_path)
            logger.info("[generate-creative] PIL fallback card written")
        except Exception as pil_err:  # noqa: BLE001
            logger.warning(f"[generate-creative] PIL fallback also failed: {pil_err}")
            return JSONResponse(
                {"status": "error", "message": "Image generation failed. Check Vertex AI access, billing, or model availability."},
                status_code=500,
            )

    cache_bust = int(time.time())
    return JSONResponse(
        {
            "status": "ok",
            "image_url": f"/creatives/{out_filename}?v={cache_bust}",
        }
    )


@app.get("/demo-assets/{filename}")
async def serve_demo_asset(filename: str):
    """Serve only basename-validated assets from the curated demo corpus."""
    safe = Path(filename).name
    path = asset_directory() / safe
    if not path.is_file():
        raise HTTPException(404, f"Demo asset not found: {safe}")
    return FileResponse(path)


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
        context=_report_context(report, report_id),
    )
