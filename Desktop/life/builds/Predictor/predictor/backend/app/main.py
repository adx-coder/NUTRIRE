"""
Predictor - ML-Powered Analytics Platform

Central ML App Store for the enterprise. Pluggable architecture for
multiple ML models with beautiful visualizations and analytics.
"""

import sys
from pathlib import Path

# Add project root for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.storage import ensure_bucket
from app.database import init_db
from app.routers import auth, admin, events, exports, models, runs
from app.routers.model_library import router as model_library_router
from app.routers.versions import router as versions_router
from app.routers.api_keys import router as api_keys_router
from app.routers.programmatic import router as programmatic_router
from app.routers.datasets import router as datasets_router
from app.routers.data_sources import router as data_sources_router
from app.routers.agents import router as agents_router
from app.routers.simulator import router as simulator_router
from app.routers.drive_sync import router as drive_sync_router

app = FastAPI(
    title="Predictor",
    description="ML-Powered Analytics Platform - Your central hub for machine learning models",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth.router)             # /api/auth/*
app.include_router(admin.router)            # /api/admin/*
app.include_router(models.router)           # /api/models/*
app.include_router(runs.router)             # /api/runs/*
app.include_router(events.router)           # /api/events/*
app.include_router(exports.router)          # /api/exports/*
app.include_router(model_library_router)    # /api/library/*
app.include_router(versions_router)         # /api/versions/*
app.include_router(api_keys_router)         # /api/api-keys/*
app.include_router(programmatic_router)     # /api/v1/*
app.include_router(datasets_router)         # /api/datasets/*
app.include_router(data_sources_router)     # /api/data-sources/*
app.include_router(agents_router)           # /api/agents/*
app.include_router(simulator_router)        # /api/simulator/*
app.include_router(drive_sync_router)       # /api/drive/*


@app.on_event("startup")
def startup():
    init_db()
    ensure_bucket()


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "Predictor", "version": "1.0.0"}
