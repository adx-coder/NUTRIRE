"""
Data Source Connections API
============================

Endpoints:

  GET    /api/data-sources/connectors           — list all connector types + status
  GET    /api/data-sources                      — list saved connections for current tenant
  POST   /api/data-sources                      — create a new connection
  GET    /api/data-sources/{conn_id}            — get single connection detail (no credentials)
  PATCH  /api/data-sources/{conn_id}            — update a connection (name / credentials)
  DELETE /api/data-sources/{conn_id}            — delete a connection
  POST   /api/data-sources/{conn_id}/test       — test a saved connection (live)
  POST   /api/data-sources/test-credentials     — test credentials before saving
  GET    /api/data-sources/{conn_id}/browse     — browse files / tables in the source
  POST   /api/data-sources/{conn_id}/preview    — preview rows from a file / table
  POST   /api/data-sources/{conn_id}/fetch      — fetch a file/table as a dataset
                                                  (returns DatasetVersion-like metadata,
                                                   stores the data in MinIO so it can be
                                                   used exactly like an uploaded dataset)
"""

import io
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.database.users import UserAccount, Tenant
from app.database.data_sources import DataSourceConnection
from app.services.connector_service import (
    list_connector_types,
    get_connector_meta,
    test_connection,
    list_objects,
    fetch_as_dataframe,
    GoogleDriveConnector,
)
from app.services import drive_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-sources", tags=["data-sources"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ConnectionCreate(BaseModel):
    name: str
    connector_type: str
    description: str | None = None
    credentials: dict


class ConnectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    credentials: dict | None = None
    is_active: bool | None = None


class TestCredentialsRequest(BaseModel):
    connector_type: str
    credentials: dict


class PreviewRequest(BaseModel):
    path: str
    limit: int = 50


class FetchRequest(BaseModel):
    """Fetch a remote file/table and stage it as an importable dataset."""
    path: str
    file_key: str        # the file_key to assign within the training pipeline
    dataset_label: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_tenant_id(current_user: UserAccount, db: Session) -> int:
    from app.database import ROLE_SUPERADMIN
    if current_user.role == ROLE_SUPERADMIN and current_user.tenant_id is None:
        platform = db.query(Tenant).filter(Tenant.slug == "platform").first()
        if not platform:
            platform = Tenant(slug="platform", name="Platform", is_active=True, plan="enterprise")
            db.add(platform)
            db.commit()
            db.refresh(platform)
        return platform.id
    return current_user.tenant_id


def _sanitise_for_json(value):
    """Coerce a single value so it is always JSON-serialisable.

    Handles:
      - float NaN / Inf / -Inf  → None
      - numpy scalar types      → native Python int / float / bool
      - everything else         → unchanged
    """
    import math
    import numpy as np

    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        v = float(value)
        return None if not math.isfinite(v) else v
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _get_connection_or_404(conn_id: int, tenant_id: int, db: Session) -> DataSourceConnection:
    conn = db.query(DataSourceConnection).filter(
        DataSourceConnection.id == conn_id,
        DataSourceConnection.tenant_id == tenant_id,
    ).first()
    if not conn:
        raise HTTPException(404, f"Data source connection {conn_id} not found.")
    return conn


def _mask_credentials(creds: dict) -> dict:
    """Return a copy of credentials with sensitive fields replaced by '***'."""
    SENSITIVE = {"password", "service_account_json", "secret_key", "private_key", "token", "api_key"}
    masked = {}
    for k, v in creds.items():
        if k in SENSITIVE:
            masked[k] = "***" if v else ""
        else:
            masked[k] = v
    return masked


def _serialize_connection(conn: DataSourceConnection, show_masked_creds: bool = True) -> dict:
    d = conn.to_dict()
    if show_masked_creds:
        d["credentials_masked"] = _mask_credentials(conn.credentials_dict)
    return d


# ---------------------------------------------------------------------------
# Connector catalogue
# ---------------------------------------------------------------------------

@router.get("/connectors")
def get_connector_types():
    """Return the full catalogue of connector types, available + coming-soon."""
    return list_connector_types()


# ---------------------------------------------------------------------------
# CRUD — connections
# ---------------------------------------------------------------------------

@router.get("")
def list_connections(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """List all saved data source connections for the current tenant."""
    tenant_id = _resolve_tenant_id(current_user, db)
    connections = (
        db.query(DataSourceConnection)
        .filter(DataSourceConnection.tenant_id == tenant_id)
        .order_by(DataSourceConnection.created_at.desc())
        .all()
    )
    return [_serialize_connection(c) for c in connections]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_connection(
    body: ConnectionCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Save a new data source connection."""
    meta = get_connector_meta(body.connector_type)
    if not meta:
        raise HTTPException(400, f"Unknown connector type: '{body.connector_type}'")
    if meta["status"] == "coming_soon":
        raise HTTPException(400, f"Connector '{body.connector_type}' is not yet available.")

    tenant_id = _resolve_tenant_id(current_user, db)

    conn = DataSourceConnection(
        tenant_id=tenant_id,
        name=body.name.strip(),
        connector_type=body.connector_type,
        description=body.description,
        credentials=json.dumps(body.credentials),
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return _serialize_connection(conn)



# ---------------------------------------------------------------------------
# Linked Data Sources - MUST be registered before /{conn_id} wildcard routes
# so that /linked-to-model is not swallowed by the int path param.
# ---------------------------------------------------------------------------

class LinkedDataSourceCreate(BaseModel):
    model_id: str
    path: str
    label: str | None = None
    file_key: str | None = None   # override auto-derived key if needed


@router.post("/link-to-model", status_code=status.HTTP_201_CREATED)
def link_data_source_to_model(
    conn_id: int,
    body: LinkedDataSourceCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Link a data source connection to an ML model for easy re-training.

    On first link:
      - Saves the link record.
      - Immediately fetches the current data and stores it as the initial
        snapshot (a DatasetVersion tagged as a linked-source snapshot).

    If the same (conn_id, model_id) combo is re-linked, the link metadata
    is updated but a new snapshot is NOT created automatically (use the
    /refresh endpoint for that).
    """
    import io as _io
    from app.database.linked_data_sources import LinkedDataSource
    from app.services.dataset_service import persist_dataset_version
    from app.ml_plugins.registry import get_plugin

    tenant_id = _resolve_tenant_id(current_user, db)
    conn = _get_connection_or_404(conn_id, tenant_id, db)

    if not conn.is_active:
        raise HTTPException(400, "This connection is disabled.")

    plugin = get_plugin(body.model_id)
    if not plugin:
        raise HTTPException(404, f"Model '{body.model_id}' not found.")

    # Derive file_key from the path if not explicitly supplied
    source_name = body.path.split("/")[-1] or "data"
    source_base = source_name.rsplit(".", 1)[0] if "." in source_name else source_name
    auto_file_key = source_base.replace(" ", "_").replace("-", "_").lower()
    file_key = body.file_key or auto_file_key
    source_name_csv = source_name if source_name.endswith(".csv") else source_name + ".csv"

    # Determine if this exact (connection, model, path) triple already exists.
    # Using path in the lookup means different tables from the same connection
    # each get their own independent link record.
    existing = db.query(LinkedDataSource).filter(
        LinkedDataSource.connection_id == conn_id,
        LinkedDataSource.model_id == body.model_id,
        LinkedDataSource.path == body.path,
    ).first()

    is_new_link = existing is None

    if existing:
        # Update metadata only — do NOT re-snapshot automatically
        existing.path = body.path
        existing.label = body.label
        existing.file_key = file_key
        existing.created_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        link = existing
        snapshot_result = None
    else:
        # Create the link record first (without snapshot_dataset_id yet)
        link = LinkedDataSource(
            connection_id=conn_id,
            model_id=body.model_id,
            path=body.path,
            label=body.label,
            file_key=file_key,
            snapshot_dataset_id=None,
            created_at=datetime.utcnow(),
        )
        db.add(link)
        db.commit()
        db.refresh(link)

        # Now take the initial snapshot
        try:
            df, raw_size = fetch_as_dataframe(conn.connector_type, conn.credentials_dict, body.path)

            buf = _io.BytesIO()
            df.to_csv(buf, index=False)
            csv_bytes = buf.getvalue()

            snap_label = (
                body.label
                or f"[{conn.name}] {source_name_csv} — initial snapshot {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
            )

            ds = persist_dataset_version(
                model_id=body.model_id,
                tenant_id=tenant_id,
                label=snap_label,
                uploaded_files={
                    file_key: (df, source_name_csv, csv_bytes),
                },
                db=db,
            )

            # Back-fill the snapshot ID onto the link record
            link.snapshot_dataset_id = ds.id
            db.commit()
            db.refresh(link)

            snapshot_result = {
                "dataset_id": ds.id,
                "dataset_label": ds.label,
                "rows": len(df),
                "size_bytes": raw_size,
            }
        except Exception as exc:
            logger.warning(
                "Initial snapshot failed for link %d (conn=%d, model=%s): %s",
                link.id, conn_id, body.model_id, exc,
            )
            snapshot_result = None

    result = {
        **link.to_dict(),
        "connection_name": conn.name,
        "connector_type": conn.connector_type,
        "is_new_link": is_new_link,
    }
    if snapshot_result:
        result["initial_snapshot"] = snapshot_result
    return result


@router.get("/linked-to-model")
def list_linked_data_sources(
    model_id: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """List all data sources linked to a specific model, with all snapshot dataset IDs.

    Returns each link enriched with:
      - connection_name, connector_type, connection_active
      - snapshot_dataset  : the initial snapshot DatasetVersion detail
      - all_snapshot_ids  : list of ALL dataset IDs that were ever snapshotted for
                            this link (initial + every refresh). The frontend uses
                            this to exclude linked-source snapshots from the
                            "Include previous datasets" checklist.
    """
    from app.database.linked_data_sources import LinkedDataSource
    from app.database.dataset_versions import DatasetVersion as DSV

    tenant_id = _resolve_tenant_id(current_user, db)

    links = db.query(LinkedDataSource).filter(
        LinkedDataSource.model_id == model_id,
    ).all()

    # Collect all snapshot dataset IDs across ALL links for this model so the
    # frontend can identify and separate them from regular uploaded datasets.
    # Strategy: snapshots produced by linked sources carry labels starting with
    # "[<conn_name>]". We also always store the initial snapshot_dataset_id on
    # the link record. Query all datasets whose label pattern matches.
    from app.database.dataset_versions import DatasetVersion as DSV2
    linked_conn_names = set()
    initial_snapshot_ids = set()
    for lnk in links:
        c = db.query(DataSourceConnection).filter(
            DataSourceConnection.id == lnk.connection_id
        ).first()
        if c:
            linked_conn_names.add(c.name)
        if lnk.snapshot_dataset_id:
            initial_snapshot_ids.add(lnk.snapshot_dataset_id)

    # Find all datasets for this model whose label starts with any linked conn name
    all_linked_snapshot_ids: set[int] = set(initial_snapshot_ids)
    if linked_conn_names:
        all_ds = db.query(DSV2).filter(
            DSV2.model_id == model_id,
            DSV2.is_deleted == False,
        ).all()
        for ds in all_ds:
            if ds.label:
                for cname in linked_conn_names:
                    if ds.label.startswith(f"[{cname}]"):
                        all_linked_snapshot_ids.add(ds.id)
                        break

    result = []
    for link in links:
        conn = db.query(DataSourceConnection).filter(
            DataSourceConnection.id == link.connection_id,
        ).first()
        if not conn:
            continue

        row = {
            **link.to_dict(),
            "connection_name": conn.name,
            "connector_type": conn.connector_type,
            "connection_active": conn.is_active,
            "all_snapshot_ids": sorted(all_linked_snapshot_ids),
        }

        # Attach initial snapshot detail
        if link.snapshot_dataset_id:
            snap = db.query(DSV).filter(DSV.id == link.snapshot_dataset_id).first()
            if snap:
                row["snapshot_dataset"] = {
                    "id": snap.id,
                    "label": snap.label,
                    "total_row_count": snap.total_row_count,
                    "total_size_bytes": snap.total_size_bytes,
                    "file_count": snap.file_count,
                    "created_at": snap.created_at.isoformat() if snap.created_at else None,
                }

        result.append(row)

    return result


@router.delete("/linked-to-model/{link_id}")
def unlink_data_source(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Unlink a data source from a model."""
    from app.database.linked_data_sources import LinkedDataSource

    tenant_id = _resolve_tenant_id(current_user, db)

    link = db.query(LinkedDataSource).filter(
        LinkedDataSource.id == link_id,
    ).first()

    if not link:
        raise HTTPException(404, "Link not found")

    # Verify ownership via the connection's tenant
    conn = db.query(DataSourceConnection).filter(
        DataSourceConnection.id == link.connection_id,
        DataSourceConnection.tenant_id == tenant_id,
    ).first()

    if not conn:
        raise HTTPException(404, "Link not found")

    db.delete(link)
    db.commit()
    return {"status": "deleted", "id": link_id}


@router.post("/linked-to-model/{link_id}/refresh")
def fetch_linked_data_source_snapshot(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Fetch a fresh snapshot from a linked data source and stage it as a new DatasetVersion.

    The new DatasetVersion appears in the model's dataset versioning list and can be
    selected for a training run just like any other saved dataset.
    """
    from datetime import datetime as _dt
    from app.database.linked_data_sources import LinkedDataSource
    from app.services.dataset_service import persist_dataset_version

    tenant_id = _resolve_tenant_id(current_user, db)

    link = db.query(LinkedDataSource).filter(
        LinkedDataSource.id == link_id,
    ).first()

    if not link:
        raise HTTPException(404, "Link not found")

    conn = db.query(DataSourceConnection).filter(
        DataSourceConnection.id == link.connection_id,
        DataSourceConnection.tenant_id == tenant_id,
    ).first()

    if not conn:
        raise HTTPException(404, "Data source connection not found")

    if not conn.is_active:
        raise HTTPException(400, "This connection is disabled")

    # Derive file_key — prefer stored one, fall back to path basename
    source_name = link.path.split("/")[-1] or "data.csv"
    source_name_csv = source_name if source_name.endswith(".csv") else source_name + ".csv"
    file_key = link.file_key or source_name.rsplit(".", 1)[0].replace(" ", "_").lower()

    # Fetch latest data
    df, raw_size = fetch_as_dataframe(conn.connector_type, conn.credentials_dict, link.path)

    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    csv_bytes = buf.getvalue()

    snap_label = (
        (link.label + " — " if link.label else f"[{conn.name}] {source_name_csv} — ")
        + f"snapshot {_dt.utcnow().strftime('%Y-%m-%d %H:%M')}"
    )

    ds = persist_dataset_version(
        model_id=link.model_id,
        tenant_id=tenant_id,
        label=snap_label,
        uploaded_files={
            file_key: (df, source_name_csv, csv_bytes),
        },
        db=db,
    )

    return {
        "status": "staged",
        "dataset_id": ds.id,
        "dataset_label": ds.label,
        "rows": len(df),
        "size_bytes": raw_size,
    }


# ---------------------------------------------------------------------------
# Google Drive — env-driven endpoints (no per-tenant connection required)
# These let a Colab notebook or operator browse + import Drive datasets
# using the credentials configured at the process level.
# ---------------------------------------------------------------------------

class DriveConnectRequest(BaseModel):
    client_secrets_path: str | None = None
    redirect_uri: str | None = None
    auth_code: str | None = None  # if set, exchange the code and persist token


class DriveListRequest(BaseModel):
    folder_id: str | None = None


class DriveImportRequest(BaseModel):
    file_id: str
    sheet_name: str | None = None
    file_key: str
    model_id: str
    dataset_label: str | None = None


@router.post("/drive/connect")
def drive_connect(
    body: DriveConnectRequest,
    current_user: UserAccount = Depends(get_current_user),
):
    """Drive OAuth helper.

    - Without `auth_code`: returns the authorization URL the user should visit.
    - With `auth_code`: exchanges the code for a refresh token and caches it.
    Service-account auth needs no flow — the env var alone is sufficient.
    """
    if drive_auth.is_authenticated() and not body.auth_code:
        return {"status": "already_authenticated", **drive_auth.auth_status()}

    if not body.client_secrets_path:
        raise HTTPException(
            400,
            "client_secrets_path is required to start the OAuth flow.",
        )

    flow = drive_auth.build_oauth_flow(
        body.client_secrets_path, redirect_uri=body.redirect_uri,
    )
    if body.auth_code:
        flow.fetch_token(code=body.auth_code)
        creds = flow.credentials
        path = drive_auth.save_oauth_token(creds.to_json())
        return {"status": "authenticated", "token_path": str(path)}

    auth_url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent",
    )
    return {"status": "auth_required", "authorization_url": auth_url}


@router.post("/drive/list")
def drive_list(
    body: DriveListRequest,
    current_user: UserAccount = Depends(get_current_user),
):
    conn = GoogleDriveConnector()
    if not conn.is_authenticated():
        raise HTTPException(401, "Google Drive is not authenticated.")
    try:
        return {"folder_id": body.folder_id, "items": conn.list_objects(body.folder_id)}
    except Exception as exc:
        logger.exception("Drive list failed")
        raise HTTPException(500, f"Drive list failed: {exc}")


@router.post("/drive/import")
def drive_import(
    body: DriveImportRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Import a Drive file as a DatasetVersion for `model_id`."""
    from app.ml_plugins.registry import get_plugin
    from app.services.dataset_service import persist_dataset_version

    conn = GoogleDriveConnector()
    if not conn.is_authenticated():
        raise HTTPException(401, "Google Drive is not authenticated.")

    plugin = get_plugin(body.model_id)
    if not plugin:
        raise HTTPException(404, f"Model '{body.model_id}' not found.")

    tenant_id = _resolve_tenant_id(current_user, db)

    try:
        df, raw_size = conn.fetch_as_dataframe_with_size(body.file_id, sheet_name=body.sheet_name)
    except Exception as exc:
        logger.exception("Drive import failed for file_id=%s", body.file_id)
        raise HTTPException(500, f"Drive import failed: {exc}")

    # Drive doesn't always give us a friendly file extension; fall back to .csv
    # since persist_dataset_version stores rows as CSV regardless.
    source_name = f"drive_{body.file_id}.csv"
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    csv_bytes = buf.getvalue()

    label = body.dataset_label or (
        f"[Drive] {body.file_id} — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    )

    ds = persist_dataset_version(
        model_id=body.model_id,
        tenant_id=tenant_id,
        label=label,
        uploaded_files={body.file_key: (df, source_name, csv_bytes)},
        db=db,
    )
    return {
        "status":        "staged",
        "dataset_id":    ds.id,
        "dataset_label": ds.label,
        "model_id":      body.model_id,
        "file_key":      body.file_key,
        "rows":          len(df),
        "size_bytes":    raw_size,
        "source":        f"drive://{body.file_id}",
    }


# ---------------------------------------------------------------------------
# CRUD — single connection detail / update / delete (/{conn_id} wildcard)
# These MUST come after all fixed-path routes above.
# ---------------------------------------------------------------------------

@router.get("/{conn_id}")
def get_connection(
    conn_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Get a single connection's detail. Credentials are masked."""
    tenant_id = _resolve_tenant_id(current_user, db)
    conn = _get_connection_or_404(conn_id, tenant_id, db)
    return _serialize_connection(conn)


@router.patch("/{conn_id}")
def update_connection(
    conn_id: int,
    body: ConnectionUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Update a connection's name, description, credentials, or active state."""
    tenant_id = _resolve_tenant_id(current_user, db)
    conn = _get_connection_or_404(conn_id, tenant_id, db)

    if body.name is not None:
        conn.name = body.name.strip()
    if body.description is not None:
        conn.description = body.description
    if body.is_active is not None:
        conn.is_active = body.is_active
    if body.credentials is not None:
        # Merge new credentials over existing ones so partial updates work.
        # Sensitive fields (password, service_account_json, etc.) that arrive
        # as an empty string or None mean "keep existing value" — the frontend
        # blanks them out when editing so the user doesn't see the masked '***'
        # value, but an empty submission should NOT wipe the stored secret.
        SENSITIVE_KEYS = {"password", "service_account_json", "secret_key", "private_key", "token", "api_key"}
        existing = conn.credentials_dict
        merged = dict(existing)
        for k, v in body.credentials.items():
            if k in SENSITIVE_KEYS and (v == "" or v is None):
                # Leave the existing stored value intact
                continue
            merged[k] = v
        conn.credentials = json.dumps(merged)

    conn.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conn)
    return _serialize_connection(conn)


@router.delete("/{conn_id}", status_code=status.HTTP_200_OK)
def delete_connection(
    conn_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Permanently delete a data source connection."""
    tenant_id = _resolve_tenant_id(current_user, db)
    conn = _get_connection_or_404(conn_id, tenant_id, db)
    db.delete(conn)
    db.commit()
    return {"status": "deleted", "id": conn_id}


# ---------------------------------------------------------------------------
# Test endpoints
# ---------------------------------------------------------------------------

@router.post("/test-credentials")
def test_credentials_before_save(
    body: TestCredentialsRequest,
    current_user: UserAccount = Depends(get_current_user),
):
    """Test-drive credentials without saving them. Useful during the setup wizard."""
    meta = get_connector_meta(body.connector_type)
    if not meta:
        raise HTTPException(400, f"Unknown connector type: '{body.connector_type}'")
    if meta["status"] == "coming_soon":
        raise HTTPException(400, f"Connector '{body.connector_type}' is not yet available.")

    result = test_connection(body.connector_type, body.credentials)
    return result


@router.post("/{conn_id}/test")
def test_saved_connection(
    conn_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Test a saved connection live and update its last_test_ok status."""
    tenant_id = _resolve_tenant_id(current_user, db)
    conn = _get_connection_or_404(conn_id, tenant_id, db)

    result = test_connection(conn.connector_type, conn.credentials_dict)

    conn.last_tested_at = datetime.utcnow()
    conn.last_test_ok = result["ok"]
    conn.last_test_error = result.get("error") if not result["ok"] else None
    conn.updated_at = datetime.utcnow()
    db.commit()

    return result


# ---------------------------------------------------------------------------
# Browse + Preview
# ---------------------------------------------------------------------------

@router.get("/{conn_id}/links")
def list_connection_links(
    conn_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Return all linked-data-source records for this connection.

    Used by the Integrations browser to show a badge on each table/file
    row that has already been linked to one or more models.

    Returns a dict keyed by path:
        {
          "public.invoices": [
            { "model_id": "billing_anomaly", "model_name": "Billing Anomaly", "file_key": "invoices", "link_id": 3 },
            ...
          ],
          ...
        }
    """
    from app.database.linked_data_sources import LinkedDataSource
    from app.database.ml_models import MLModel

    tenant_id = _resolve_tenant_id(current_user, db)
    # Ownership check
    _get_connection_or_404(conn_id, tenant_id, db)

    links = db.query(LinkedDataSource).filter(
        LinkedDataSource.connection_id == conn_id,
    ).all()

    result: dict[str, list] = {}
    for link in links:
        # Fetch a human-readable model name
        model_row = db.query(MLModel).filter(MLModel.id == link.model_id).first()
        model_name = model_row.name if model_row else link.model_id

        entry = {
            "link_id":   link.id,
            "model_id":  link.model_id,
            "model_name": model_name,
            "file_key":  link.file_key,
            "label":     link.label,
        }
        result.setdefault(link.path, []).append(entry)

    return result


@router.get("/{conn_id}/browse")
def browse_connection(
    conn_id: int,
    path: str = Query("", description="Sub-path to browse (e.g. GCS prefix or Postgres schema)"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Browse files / tables / schemas in the data source.

    Returns a flat list of items at `path`.  Each item has:
        { name, path, type ('file'|'folder'), size, modified, extension }
    """
    tenant_id = _resolve_tenant_id(current_user, db)
    conn = _get_connection_or_404(conn_id, tenant_id, db)

    if not conn.is_active:
        raise HTTPException(400, "This connection is disabled.")

    try:
        items = list_objects(conn.connector_type, conn.credentials_dict, path)
    except NotImplementedError as e:
        raise HTTPException(501, str(e))
    except Exception as exc:
        logger.exception("Browse failed for connection %d", conn_id)
        raise HTTPException(500, f"Browse failed: {exc}")

    return {"path": path, "items": items}


@router.post("/{conn_id}/preview")
def preview_connection_file(
    conn_id: int,
    body: PreviewRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Fetch the first N rows from a file or table for preview."""
    tenant_id = _resolve_tenant_id(current_user, db)
    conn = _get_connection_or_404(conn_id, tenant_id, db)

    if not conn.is_active:
        raise HTTPException(400, "This connection is disabled.")

    limit = min(body.limit, 500)  # safety cap

    try:
        df, _ = fetch_as_dataframe(conn.connector_type, conn.credentials_dict, body.path)
    except NotImplementedError as e:
        raise HTTPException(501, str(e))
    except Exception as exc:
        logger.exception("Preview failed for connection %d path=%s", conn_id, body.path)
        raise HTTPException(500, f"Preview failed: {exc}")

    preview_df = df.head(limit).copy()

    # Replace NaN / Inf / -Inf and numpy scalars so the JSON encoder never
    # hits a ValueError (pandas notna() misses Inf/-Inf).
    sanitised_rows = [
        {col: _sanitise_for_json(row[col]) for col in preview_df.columns}
        for row in preview_df.to_dict(orient="records")
    ]

    return {
        "path":         body.path,
        "total_rows":   len(df),
        "preview_rows": limit,
        "columns":      list(df.columns),
        "dtypes":       {c: str(df[c].dtype) for c in df.columns},
        "rows":         sanitised_rows,
    }


# ---------------------------------------------------------------------------
# Fetch — stage remote data into MinIO as an importable DatasetVersion
# ---------------------------------------------------------------------------

@router.post("/{conn_id}/fetch")
def fetch_and_stage(
    conn_id: int,
    body: FetchRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Fetch a remote file / table and stage it in MinIO as a DatasetVersion.

    This allows the training endpoint to receive a `datasource_dataset_id`
    param and use the staged data exactly like a manually uploaded file —
    without the user having to download → re-upload anything.

    Returns the DatasetVersion record so the frontend can reference it
    in the training form just like a saved historical dataset.
    """
    import pandas as pd

    from app.database.dataset_versions import DatasetVersion
    from app.services.dataset_service import persist_dataset_version

    tenant_id = _resolve_tenant_id(current_user, db)
    conn = _get_connection_or_404(conn_id, tenant_id, db)

    if not conn.is_active:
        raise HTTPException(400, "This connection is disabled.")

    # We need a model_id to scope the dataset version.
    # Since this is a standalone fetch (not tied to a specific model yet),
    # we use a special scope model_id "__datasource__" for the storage prefix.
    # When the user actually trains, they can include this dataset_id
    # via the historical_dataset_ids param just like any other saved dataset.
    # NOTE: The caller must pass model_id as a query param.
    raise HTTPException(
        501,
        "Direct fetch-to-stage is not yet wired. "
        "Use POST /api/data-sources/{conn_id}/fetch-for-model?model_id=... instead."
    )


@router.post("/{conn_id}/fetch-for-model")
async def fetch_and_stage_for_model(
    conn_id: int,
    body: FetchRequest,
    model_id: str = Query(..., description="Model ID to scope this dataset version under"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Fetch a remote file/table from the data source and persist it as a
    DatasetVersion for `model_id`.

    After this returns, the client can use `dataset_id` as a value in
    `historical_dataset_ids` when calling the train endpoint — or as the
    *only* data source for a training run (by passing it alone and omitting
    any file uploads).
    """
    import pandas as pd

    from app.ml_plugins.registry import get_plugin
    from app.services.dataset_service import persist_dataset_version

    tenant_id = _resolve_tenant_id(current_user, db)
    conn = _get_connection_or_404(conn_id, tenant_id, db)

    if not conn.is_active:
        raise HTTPException(400, "This connection is disabled.")

    # Validate model exists
    plugin = get_plugin(model_id)
    if not plugin:
        raise HTTPException(404, f"Model '{model_id}' not found.")

    # ── Fetch data from the external source ──────────────────────────────────
    try:
        df, raw_size = fetch_as_dataframe(conn.connector_type, conn.credentials_dict, body.path)
    except NotImplementedError as e:
        raise HTTPException(501, str(e))
    except Exception as exc:
        logger.exception("Fetch failed for connection %d path=%s", conn_id, body.path)
        raise HTTPException(500, f"Fetch failed: {exc}")

    # ── Serialise to CSV bytes so persist_dataset_version can store it ────────
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    csv_bytes = buf.getvalue()

    source_name = body.path.split("/")[-1] or "data.csv"
    if not source_name.endswith(".csv"):
        source_name += ".csv"

    label = body.dataset_label or (
        f"[{conn.name}] {source_name} — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    )

    # ── Persist ───────────────────────────────────────────────────────────────
    try:
        ds = persist_dataset_version(
            model_id=model_id,
            tenant_id=tenant_id,
            label=label,
            uploaded_files={
                body.file_key: (df, source_name, csv_bytes),
            },
            db=db,
        )
    except Exception as exc:
        logger.exception("Failed to persist fetched dataset")
        raise HTTPException(500, f"Failed to stage dataset: {exc}")

    # Tag the dataset with datasource metadata in the label/description (stored in label for now)
    from app.database.dataset_versions import DatasetVersion as DSV
    ds_record = db.query(DSV).filter(DSV.id == ds.id).first()

    return {
        "status":          "staged",
        "dataset_id":      ds.id,
        "dataset_label":   ds.label,
        "model_id":        model_id,
        "file_key":        body.file_key,
        "rows":            len(df),
        "size_bytes":      raw_size,
        "source":          body.path,
        "connection_name": conn.name,
        "connector_type":  conn.connector_type,
"note": (
            f"Data from '{conn.name}' has been staged as dataset #{ds.id}. "
            "You can now include it in a training run using historical_dataset_ids."
        ),
    }