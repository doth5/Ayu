"""
FastAPI application entry point.
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from app.database.database import init_db
from app.core.scheduler import start_scheduler, stop_scheduler
from app.api.routers import doctors, pipelines, templates, media, dashboard, executions, campaigns

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


def _auto_launch_whatsapp():
    """Open WhatsApp Web browser in the background at server startup."""
    try:
        import time as _time
        _time.sleep(3)  # Give uvicorn a moment to finish binding
        from app.core.whatsapp_web import wa_web_open_for_setup
        logger.info("[Startup] Auto-launching WhatsApp Web browser...")
        result = wa_web_open_for_setup(qr_timeout_seconds=300)
        logger.info("[Startup] WhatsApp Web launch result: %s", result.get("status"))
    except Exception as e:
        logger.warning("[Startup] WhatsApp Web auto-launch failed (non-fatal): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import threading
    # Startup
    logger.info("Initialising database…")
    init_db()
    logger.info("Starting scheduler…")
    start_scheduler()

    # Auto-open WhatsApp Web so the browser is ready before the first campaign
    wa_thread = threading.Thread(target=_auto_launch_whatsapp, daemon=True, name="wa-startup")
    wa_thread.start()

    yield
    # Shutdown
    logger.info("Stopping scheduler…")
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local media folder for serving files
settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(settings.MEDIA_ROOT)), name="media")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(doctors.router,    prefix="/api/doctors",    tags=["Doctors"])
app.include_router(pipelines.router,  prefix="/api/pipelines",  tags=["Pipelines"])
app.include_router(templates.router,  prefix="/api/templates",  tags=["Templates"])
app.include_router(media.router,      prefix="/api/media",      tags=["Media"])
app.include_router(dashboard.router,  prefix="/api/dashboard",  tags=["Dashboard"])
app.include_router(executions.router, prefix="/api/executions", tags=["Executions"])
app.include_router(campaigns.router,  prefix="/api/campaigns",  tags=["Campaigns"])


@app.get("/", tags=["Health"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
