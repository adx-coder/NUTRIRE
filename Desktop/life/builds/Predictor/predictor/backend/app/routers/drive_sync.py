"""
Google Drive Sync API
=====================

Endpoints:

  GET  /api/drive/status                          — auth status + last sync timestamps
  POST /api/drive/models/{model_id}/sync_up       — push local model_dir → Drive folder
  POST /api/drive/models/{model_id}/sync_down     — pull Drive folder → local model_dir

The "local" model_dir is the MinIO-backed prefix for a given (model_id, version)
artifact set; we materialise it to a temp dir using `model_dir_context` and then
push/pull from Drive there.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.storage import model_dir_context
from app.database import get_db
from app.database.ml_models import ModelVersion
from app.database.users import UserAccount
from app.services.connector_service import GoogleDriveConnector
from app.services.drive_auth import auth_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drive", tags=["drive-sync"])

# In-memory last-sync log; survives until process restart. Sync history is best
# effort metadata for the UI, not authoritative state.
_LAST_SYNC: dict[str, dict[str, Any]] = {}


class SyncRequest(BaseModel):
    drive_folder_id: str
    version: int | None = None  # default: active version


def _resolve_version(model_id: str, version: int | None, db: Session) -> ModelVersion:
    q = db.query(ModelVersion).filter(ModelVersion.model_id == model_id)
    if version is not None:
        v = q.filter(ModelVersion.version == version).first()
    else:
        v = q.filter(ModelVersion.is_active == 1).order_by(ModelVersion.version.desc()).first()
    if not v:
        raise HTTPException(404, f"No model version found for '{model_id}'.")
    return v


def _require_drive() -> GoogleDriveConnector:
    conn = GoogleDriveConnector()
    if not conn.is_authenticated():
        raise HTTPException(
            401,
            "Google Drive is not authenticated. Set GOOGLE_DRIVE_CREDENTIALS_JSON "
            "or GOOGLE_DRIVE_OAUTH_TOKEN, or POST /api/data-sources/drive/connect.",
        )
    return conn


@router.get("/status")
def drive_status():
    """Return Drive auth status + last sync timestamps."""
    return {
        **auth_status(),
        "last_sync": _LAST_SYNC,
    }


@router.post("/models/{model_id}/sync_up")
def sync_model_up(
    model_id: str,
    body: SyncRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Push the local model artifact directory up to a Drive folder."""
    drive = _require_drive()
    version = _resolve_version(model_id, body.version, db)

    with model_dir_context(version.artifact_path, "r") as model_dir:
        result = drive.sync_folder_up(str(model_dir), body.drive_folder_id)

    _LAST_SYNC[f"{model_id}:up"] = {
        "model_id":         model_id,
        "version":          version.version,
        "drive_folder_id":  body.drive_folder_id,
        "synced_at":        datetime.utcnow().isoformat() + "Z",
        "file_count":       len(result["files"]),
    }
    return {
        "status":      "ok",
        "model_id":    model_id,
        "version":     version.version,
        "uploaded":    result["files"],
        "drive_folder_id": body.drive_folder_id,
    }


@router.post("/models/{model_id}/sync_down")
def sync_model_down(
    model_id: str,
    body: SyncRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Pull a Drive folder down into the local model artifact directory.

    The downloaded files replace whatever currently exists at the model
    version's MinIO prefix, so this is the operation a Colab training run
    pairs with after writing artifacts to Drive.
    """
    drive = _require_drive()
    version = _resolve_version(model_id, body.version, db)

    # mode="w" gives us a clean temp dir and uploads its contents to MinIO on exit.
    with model_dir_context(version.artifact_path, "w") as local:
        result = drive.sync_folder_down(body.drive_folder_id, str(local))

    _LAST_SYNC[f"{model_id}:down"] = {
        "model_id":         model_id,
        "version":          version.version,
        "drive_folder_id":  body.drive_folder_id,
        "synced_at":        datetime.utcnow().isoformat() + "Z",
        "file_count":       len(result["files"]),
    }
    return {
        "status":      "ok",
        "model_id":    model_id,
        "version":     version.version,
        "downloaded":  result["files"],
        "artifact_path": version.artifact_path,
    }
