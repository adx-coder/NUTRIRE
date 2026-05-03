"""
Connector Service
=================

Abstracts over all external data source types. Each connector exposes:

  test_connection(credentials)  →  { ok: bool, error: str | None, meta: dict }
  list_objects(credentials, path)  →  [ { name, path, type, size, modified } ]
  fetch_as_dataframe(credentials, path)  →  pd.DataFrame

Supported now:
  • gcs      — Google Cloud Storage
  • postgres  — PostgreSQL (any schema/table)

Coming soon (stubbed so they appear in the UI):
  s3, minio, snowflake, airtable, supabase, huggingface, google_sheets
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

CONNECTOR_REGISTRY: dict[str, dict] = {
    "gcs": {
        "label":       "Google Cloud Storage",
        "short":       "GCS",
        "description": "Connect to a Google Cloud Storage bucket and load CSV/Parquet files directly.",
        "icon":        "google_cloud",
        "status":      "available",
        "credential_fields": [
            {"key": "project_id",           "label": "GCP Project ID",      "type": "text",     "required": True,  "placeholder": "my-gcp-project"},
            {"key": "bucket_name",          "label": "Bucket Name",         "type": "text",     "required": True,  "placeholder": "my-data-bucket"},
            {"key": "service_account_json", "label": "Service Account JSON","type": "json",     "required": True,  "placeholder": '{"type":"service_account","project_id":"..."}'},
            {"key": "path_prefix",          "label": "Path Prefix (opt.)",  "type": "text",     "required": False, "placeholder": "datasets/"},
        ],
    },
    "postgres": {
        "label":       "PostgreSQL",
        "short":       "Postgres",
        "description": "Connect to any PostgreSQL database and export tables or query results as datasets.",
        "icon":        "postgres",
        "status":      "available",
        "credential_fields": [
            {"key": "host",     "label": "Host",     "type": "text",     "required": True,  "placeholder": "db.example.com"},
            {"key": "port",     "label": "Port",     "type": "number",   "required": True,  "placeholder": "5432"},
            {"key": "database", "label": "Database", "type": "text",     "required": True,  "placeholder": "mydb"},
            {"key": "user",     "label": "Username", "type": "text",     "required": True,  "placeholder": "readonly_user"},
            {"key": "password", "label": "Password", "type": "password", "required": True,  "placeholder": ""},
            {"key": "schema",   "label": "Schema (opt.)", "type": "text","required": False, "placeholder": "public"},
            {"key": "ssl_mode", "label": "SSL Mode", "type": "select",   "required": False,
             "options": ["disable", "require", "verify-ca", "verify-full"], "placeholder": "require"},
        ],
    },
    "s3": {
        "label":       "Amazon S3",
        "short":       "S3",
        "description": "Pull data directly from S3 buckets using IAM credentials or access keys.",
        "icon":        "aws_s3",
        "status":      "coming_soon",
        "credential_fields": [],
    },
    "minio": {
        "label":       "MinIO",
        "short":       "MinIO",
        "description": "Connect to a self-hosted MinIO instance to load stored datasets.",
        "icon":        "minio",
        "status":      "coming_soon",
        "credential_fields": [],
    },
    "snowflake": {
        "label":       "Snowflake",
        "short":       "Snowflake",
        "description": "Query Snowflake warehouses and load the results as training data.",
        "icon":        "snowflake",
        "status":      "coming_soon",
        "credential_fields": [],
    },
    "airtable": {
        "label":       "Airtable",
        "short":       "Airtable",
        "description": "Load Airtable bases and tables directly into the training pipeline.",
        "icon":        "airtable",
        "status":      "coming_soon",
        "credential_fields": [],
    },
    "supabase": {
        "label":       "Supabase",
        "short":       "Supabase",
        "description": "Stream data from Supabase Postgres tables or Storage buckets.",
        "icon":        "supabase",
        "status":      "coming_soon",
        "credential_fields": [],
    },
    "huggingface": {
        "label":       "Hugging Face Datasets",
        "short":       "HF Hub",
        "description": "Load public or private datasets from the Hugging Face Hub.",
        "icon":        "huggingface",
        "status":      "coming_soon",
        "credential_fields": [],
    },
    "google_sheets": {
        "label":       "Google Sheets",
        "short":       "Sheets",
        "description": "Import Google Sheets spreadsheets as tabular training data.",
        "icon":        "google_sheets",
        "status":      "coming_soon",
        "credential_fields": [],
    },
    "google_drive": {
        "label":       "Google Drive",
        "short":       "Drive",
        "description": "Browse Google Drive folders, import datasets (CSV/Excel/Sheets), and sync model artifacts to/from Drive.",
        "icon":        "google_drive",
        "status":      "available",
        "credential_fields": [
            {"key": "folder_id",            "label": "Default Folder ID (opt.)", "type": "text", "required": False, "placeholder": "1A2B3CdEfGhIjK..."},
            {"key": "service_account_json", "label": "Service Account JSON (opt., otherwise env-driven)", "type": "json", "required": False, "placeholder": '{"type":"service_account",...}'},
        ],
    },
}


def get_connector_meta(connector_type: str) -> dict | None:
    return CONNECTOR_REGISTRY.get(connector_type)


def list_connector_types() -> list[dict]:
    return [
        {
            "type":              ctype,
            "label":             meta["label"],
            "short":             meta["short"],
            "description":       meta["description"],
            "icon":              meta["icon"],
            "status":            meta["status"],
            "credential_fields": meta.get("credential_fields", []),
        }
        for ctype, meta in CONNECTOR_REGISTRY.items()
    ]


# ---------------------------------------------------------------------------
# GCS Connector
# ---------------------------------------------------------------------------

def _gcs_client(credentials: dict):
    """Build a GCS storage client from service-account credentials."""
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
    except ImportError:
        raise RuntimeError(
            "google-cloud-storage is not installed. "
            "Run: pip install google-cloud-storage"
        )

    sa_json = credentials.get("service_account_json")
    if not sa_json:
        raise ValueError("service_account_json is required for GCS connector")

    if isinstance(sa_json, str):
        sa_json = json.loads(sa_json)

    sa_credentials = service_account.Credentials.from_service_account_info(
        sa_json,
        scopes=["https://www.googleapis.com/auth/devstorage.read_only"],
    )
    return storage.Client(
        project=credentials.get("project_id"),
        credentials=sa_credentials,
    )


def gcs_test_connection(credentials: dict) -> dict:
    try:
        client = _gcs_client(credentials)
        bucket_name = credentials.get("bucket_name")
        if not bucket_name:
            return {"ok": False, "error": "bucket_name is required", "meta": {}}
        bucket = client.bucket(bucket_name)
        # List a handful of blobs to confirm access
        blobs = list(bucket.list_blobs(max_results=5, prefix=credentials.get("path_prefix", "")))
        return {
            "ok": True,
            "error": None,
            "meta": {
                "bucket": bucket_name,
                "sample_objects": len(blobs),
                "project": credentials.get("project_id"),
            },
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "meta": {}}


def gcs_list_objects(credentials: dict, path: str = "") -> list[dict]:
    """List blobs in the GCS bucket under `path`.

    Returns folders (common prefixes) and files (blobs) separately, so the
    frontend can render a directory-tree style file browser.
    """
    client = _gcs_client(credentials)
    bucket_name = credentials.get("bucket_name", "")
    prefix = credentials.get("path_prefix", "")

    # Combine the stored prefix with the browse path
    full_prefix = (prefix.rstrip("/") + "/" + path.lstrip("/")).lstrip("/")
    if full_prefix and not full_prefix.endswith("/"):
        full_prefix += "/"

    bucket = client.bucket(bucket_name)
    iterator = bucket.list_blobs(prefix=full_prefix, delimiter="/")

    results = []

    # Consume iterator to populate prefixes
    blobs = list(iterator)

    # "Folders" — common prefixes
    for p in iterator.prefixes:
        folder_name = p.rstrip("/").split("/")[-1]
        results.append({
            "name":     folder_name,
            "path":     p,
            "type":     "folder",
            "size":     None,
            "modified": None,
        })

    # Files
    for blob in blobs:
        # Skip the prefix itself (zero-size marker objects)
        if blob.name == full_prefix:
            continue
        file_name = blob.name.split("/")[-1]
        if not file_name:
            continue
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if ext not in {"csv", "parquet", "json", "jsonl", "tsv", "xlsx"}:
            # Still include, but flag as unsupported
            pass
        results.append({
            "name":      file_name,
            "path":      blob.name,
            "type":      "file",
            "size":      blob.size,
            "modified":  blob.updated.isoformat() if blob.updated else None,
            "extension": ext,
        })

    results.sort(key=lambda x: (0 if x["type"] == "folder" else 1, x["name"]))
    return results


def gcs_fetch_dataframe(credentials: dict, path: str) -> tuple[pd.DataFrame, int]:
    """Download a file from GCS and return a DataFrame + raw byte size."""
    client = _gcs_client(credentials)
    bucket_name = credentials.get("bucket_name", "")
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(path)
    raw = blob.download_as_bytes()
    df = _bytes_to_dataframe(raw, path)
    return df, len(raw)


# ---------------------------------------------------------------------------
# Postgres Connector
# ---------------------------------------------------------------------------

def _pg_engine(credentials: dict):
    try:
        from sqlalchemy import create_engine as _ce
    except ImportError:
        raise RuntimeError("sqlalchemy is not installed.")
    try:
        import psycopg2  # noqa: F401 — ensure the driver is present
    except ImportError:
        raise RuntimeError("psycopg2-binary is not installed.")

    host     = credentials.get("host", "localhost")
    port     = int(credentials.get("port", 5432))
    database = credentials.get("database", "")
    user     = credentials.get("user", "")
    password = credentials.get("password", "")
    ssl_mode = credentials.get("ssl_mode", "require")

    url = (
        f"postgresql+psycopg2://{user}:{password}"
        f"@{host}:{port}/{database}"
        f"?sslmode={ssl_mode}"
    )
    return _ce(url, connect_args={"connect_timeout": 10})


def postgres_test_connection(credentials: dict) -> dict:
    try:
        engine = _pg_engine(credentials)
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
        engine.dispose()
        return {
            "ok": True,
            "error": None,
            "meta": {"server_version": version},
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "meta": {}}


def postgres_list_objects(credentials: dict, path: str = "") -> list[dict]:
    """List schemas → tables.

    `path` interpretation:
      ""           → list all schemas
      "schema"     → list tables in that schema
    """
    engine = _pg_engine(credentials)
    target_schema = credentials.get("schema") or None

    results = []
    try:
        with engine.connect() as conn:
            from sqlalchemy import text

            if not path:
                # List schemas (or just the configured schema)
                if target_schema:
                    schemas = [target_schema]
                else:
                    rows = conn.execute(text(
                        "SELECT schema_name FROM information_schema.schemata "
                        "WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast') "
                        "ORDER BY schema_name"
                    ))
                    schemas = [r[0] for r in rows]

                for s in schemas:
                    results.append({
                        "name":     s,
                        "path":     s,
                        "type":     "folder",
                        "size":     None,
                        "modified": None,
                    })
            else:
                # List tables/views in the given schema
                schema = path.split("/")[0]
                rows = conn.execute(text(
                    "SELECT table_name, table_type "
                    "FROM information_schema.tables "
                    "WHERE table_schema = :schema "
                    "ORDER BY table_name"
                ), {"schema": schema})
                for row in rows:
                    tname, ttype = row[0], row[1]
                    # Get approximate row count from pg_class stats
                    try:
                        rc = conn.execute(text(
                            "SELECT reltuples::bigint FROM pg_class c "
                            "JOIN pg_namespace n ON n.oid = c.relnamespace "
                            "WHERE n.nspname = :schema AND c.relname = :table"
                        ), {"schema": schema, "table": tname}).scalar()
                        row_count = int(rc) if rc and rc > 0 else None
                    except Exception:
                        row_count = None

                    results.append({
                        "name":      tname,
                        "path":      f"{schema}/{tname}",
                        "type":      "file",
                        "size":      None,
                        "row_count": row_count,
                        "modified":  None,
                        "extension": "table" if ttype == "BASE TABLE" else "view",
                    })
    finally:
        engine.dispose()

    return results


def postgres_fetch_dataframe(credentials: dict, path: str) -> tuple[pd.DataFrame, int]:
    """Fetch a table from Postgres as a DataFrame.

    `path` format: "schema/table"
    """
    parts = path.split("/")
    if len(parts) != 2:
        raise ValueError(f"Expected path format 'schema/table', got: {path!r}")
    schema, table = parts[0], parts[1]

    engine = _pg_engine(credentials)
    try:
        df = pd.read_sql_table(table, con=engine, schema=schema)
    finally:
        engine.dispose()

    # Estimate CSV-equivalent byte size
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    size = buf.tell()
    return df, size


# ---------------------------------------------------------------------------
# Dispatch helpers
# ---------------------------------------------------------------------------

def test_connection(connector_type: str, credentials: dict) -> dict:
    if connector_type == "gcs":
        return gcs_test_connection(credentials)
    if connector_type == "postgres":
        return postgres_test_connection(credentials)
    if connector_type == "google_drive":
        return GoogleDriveConnector(credentials).test_connection()
    return {"ok": False, "error": f"Connector type '{connector_type}' is not yet implemented.", "meta": {}}


def list_objects(connector_type: str, credentials: dict, path: str = "") -> list[dict]:
    if connector_type == "gcs":
        return gcs_list_objects(credentials, path)
    if connector_type == "postgres":
        return postgres_list_objects(credentials, path)
    if connector_type == "google_drive":
        return GoogleDriveConnector(credentials).list_objects(path or None)
    raise NotImplementedError(f"Connector type '{connector_type}' is not yet implemented.")


def fetch_as_dataframe(connector_type: str, credentials: dict, path: str) -> tuple[pd.DataFrame, int]:
    if connector_type == "gcs":
        return gcs_fetch_dataframe(credentials, path)
    if connector_type == "postgres":
        return postgres_fetch_dataframe(credentials, path)
    if connector_type == "google_drive":
        return GoogleDriveConnector(credentials).fetch_as_dataframe_with_size(path)
    raise NotImplementedError(f"Connector type '{connector_type}' is not yet implemented.")


# ---------------------------------------------------------------------------
# Format parsing helper
# ---------------------------------------------------------------------------

def _bytes_to_dataframe(raw: bytes, filename: str) -> pd.DataFrame:
    """Parse raw file bytes into a DataFrame based on the file extension."""
    fn = filename.lower()
    if fn.endswith(".parquet"):
        return pd.read_parquet(io.BytesIO(raw))
    if fn.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(raw))
    if fn.endswith(".jsonl") or fn.endswith(".ndjson"):
        return pd.read_json(io.BytesIO(raw), lines=True)
    if fn.endswith(".json"):
        return pd.read_json(io.BytesIO(raw))
    if fn.endswith(".tsv"):
        return pd.read_csv(io.BytesIO(raw), sep="\t")
    # Default: CSV
    return pd.read_csv(io.BytesIO(raw))


# ---------------------------------------------------------------------------
# Google Drive Connector
# ---------------------------------------------------------------------------

# Drive MIME types we can usefully expose as datasets.
_DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
_DRIVE_SHEET_MIME  = "application/vnd.google-apps.spreadsheet"
_DRIVE_DOC_MIME    = "application/vnd.google-apps.document"

_TABULAR_EXTS = {"csv", "tsv", "json", "jsonl", "ndjson", "parquet", "xlsx", "xls"}


class GoogleDriveConnector:
    """Drive connector for datasets and model-artifact sync.

    Credentials precedence:
      1. `service_account_json` in the per-connection credentials dict
      2. environment-driven auth via `app.services.drive_auth`
    """

    def __init__(self, credentials: dict | None = None):
        self._creds_dict = credentials or {}
        self._service = None
        self._creds = None

    # ── Auth ────────────────────────────────────────────────────────────────

    def _build_credentials(self):
        if self._creds is not None:
            return self._creds
        sa_json = self._creds_dict.get("service_account_json") if self._creds_dict else None
        if sa_json:
            try:
                from google.oauth2 import service_account
            except ImportError:
                raise RuntimeError("google-auth is not installed.")
            if isinstance(sa_json, str):
                sa_json = json.loads(sa_json)
            from app.services.drive_auth import DEFAULT_SCOPES
            self._creds = service_account.Credentials.from_service_account_info(
                sa_json, scopes=DEFAULT_SCOPES,
            )
            return self._creds

        from app.services.drive_auth import get_credentials
        self._creds = get_credentials()
        return self._creds

    def is_authenticated(self) -> bool:
        try:
            return self._build_credentials() is not None
        except Exception:
            return False

    def _client(self):
        if self._service is not None:
            return self._service
        creds = self._build_credentials()
        if creds is None:
            raise RuntimeError(
                "Google Drive is not authenticated. Set GOOGLE_DRIVE_CREDENTIALS_JSON "
                "or GOOGLE_DRIVE_OAUTH_TOKEN, or supply service_account_json in the connection."
            )
        try:
            from googleapiclient.discovery import build
        except ImportError:
            raise RuntimeError(
                "google-api-python-client is not installed. "
                "Run: pip install google-api-python-client"
            )
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    # ── Lifecycle helpers ───────────────────────────────────────────────────

    def test_connection(self) -> dict:
        try:
            svc = self._client()
            about = svc.about().get(fields="user(emailAddress,displayName), storageQuota").execute()
            return {
                "ok": True,
                "error": None,
                "meta": {
                    "user": about.get("user", {}),
                    "storage_quota": about.get("storageQuota", {}),
                },
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "meta": {}}

    # ── Browse ──────────────────────────────────────────────────────────────

    def list_objects(self, folder_id: str | None = None) -> list[dict]:
        svc = self._client()
        parent = folder_id or self._creds_dict.get("folder_id") or "root"
        q = f"'{parent}' in parents and trashed = false"
        results: list[dict] = []
        page_token: str | None = None
        while True:
            resp = svc.files().list(
                q=q,
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)",
                pageSize=200,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            for f in resp.get("files", []):
                is_folder = f["mimeType"] == _DRIVE_FOLDER_MIME
                ext = ""
                if not is_folder and "." in f["name"]:
                    ext = f["name"].rsplit(".", 1)[-1].lower()
                results.append({
                    "id":        f["id"],
                    "name":      f["name"],
                    "path":      f["id"],
                    "type":      "folder" if is_folder else "file",
                    "mime_type": f["mimeType"],
                    "size":      int(f["size"]) if f.get("size") else None,
                    "modified":  f.get("modifiedTime"),
                    "extension": ext,
                })
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        results.sort(key=lambda x: (0 if x["type"] == "folder" else 1, x["name"].lower()))
        return results

    # ── Fetch as DataFrame ──────────────────────────────────────────────────

    def fetch_as_dataframe(self, file_id: str, sheet_name: str | None = None) -> pd.DataFrame:
        df, _ = self.fetch_as_dataframe_with_size(file_id, sheet_name=sheet_name)
        return df

    def fetch_as_dataframe_with_size(
        self,
        file_id: str,
        sheet_name: str | None = None,
    ) -> tuple[pd.DataFrame, int]:
        svc = self._client()
        meta = svc.files().get(
            fileId=file_id,
            fields="id, name, mimeType, size",
            supportsAllDrives=True,
        ).execute()

        mime = meta["mimeType"]
        name = meta["name"]

        if mime == _DRIVE_SHEET_MIME:
            # Export Google Sheet as XLSX so we can pick a sheet by name.
            raw = svc.files().export(
                fileId=file_id,
                mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ).execute()
            df = pd.read_excel(io.BytesIO(raw), sheet_name=sheet_name or 0)
            return df, len(raw)

        if mime == _DRIVE_DOC_MIME:
            raise ValueError("Google Docs cannot be loaded as a DataFrame.")

        raw = self._download_bytes(file_id)
        if name.lower().endswith((".xlsx", ".xls")) and sheet_name is not None:
            df = pd.read_excel(io.BytesIO(raw), sheet_name=sheet_name)
        else:
            df = _bytes_to_dataframe(raw, name)
        return df, len(raw)

    # ── File transfer ───────────────────────────────────────────────────────

    def _download_bytes(self, file_id: str) -> bytes:
        from googleapiclient.http import MediaIoBaseDownload
        svc = self._client()
        request = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()

    def download_file(self, file_id: str, dest_path: str) -> str:
        import os
        svc = self._client()
        meta = svc.files().get(fileId=file_id, fields="name, mimeType", supportsAllDrives=True).execute()
        target = dest_path
        # If dest is an existing dir or has no extension, append the source filename.
        if os.path.isdir(dest_path):
            target = os.path.join(dest_path, meta["name"])
        else:
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)

        if meta["mimeType"] == _DRIVE_SHEET_MIME:
            raw = svc.files().export(
                fileId=file_id,
                mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ).execute()
            if not target.lower().endswith((".xlsx", ".xls")):
                target = target + ".xlsx"
            with open(target, "wb") as fh:
                fh.write(raw)
        else:
            raw = self._download_bytes(file_id)
            with open(target, "wb") as fh:
                fh.write(raw)
        return target

    def upload_file(
        self,
        local_path: str,
        folder_id: str | None = None,
        name: str | None = None,
    ) -> str:
        from googleapiclient.http import MediaFileUpload
        import mimetypes
        import os

        svc = self._client()
        target_folder = folder_id or self._creds_dict.get("folder_id")
        upload_name = name or os.path.basename(local_path)
        mime_type, _ = mimetypes.guess_type(local_path)
        media = MediaFileUpload(
            local_path, mimetype=mime_type or "application/octet-stream", resumable=True,
        )
        body: dict[str, Any] = {"name": upload_name}
        if target_folder:
            body["parents"] = [target_folder]

        # Replace if a same-named file already exists in the target folder.
        existing_id = self._find_in_folder(upload_name, target_folder) if target_folder else None
        if existing_id:
            updated = svc.files().update(
                fileId=existing_id, media_body=media, supportsAllDrives=True,
            ).execute()
            return updated["id"]

        created = svc.files().create(
            body=body, media_body=media, fields="id", supportsAllDrives=True,
        ).execute()
        return created["id"]

    def _find_in_folder(self, name: str, folder_id: str) -> str | None:
        svc = self._client()
        # Drive query strings need single quotes escaped.
        safe_name = name.replace("'", "\\'")
        q = f"name = '{safe_name}' and '{folder_id}' in parents and trashed = false"
        resp = svc.files().list(
            q=q, fields="files(id, name)", pageSize=1,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        files = resp.get("files", [])
        return files[0]["id"] if files else None

    def create_folder(self, name: str, parent_id: str | None = None) -> str:
        svc = self._client()
        parent = parent_id or self._creds_dict.get("folder_id")
        existing = self._find_in_folder(name, parent) if parent else None
        if existing:
            # Reject if the existing item isn't actually a folder.
            meta = svc.files().get(fileId=existing, fields="mimeType", supportsAllDrives=True).execute()
            if meta["mimeType"] == _DRIVE_FOLDER_MIME:
                return existing
        body: dict[str, Any] = {"name": name, "mimeType": _DRIVE_FOLDER_MIME}
        if parent:
            body["parents"] = [parent]
        created = svc.files().create(body=body, fields="id", supportsAllDrives=True).execute()
        return created["id"]

    # ── Folder sync ─────────────────────────────────────────────────────────

    def sync_folder_down(self, drive_folder_id: str, local_dir: str) -> dict:
        """Recursively pull a Drive folder into local_dir."""
        import os
        os.makedirs(local_dir, exist_ok=True)
        files = self.list_objects(drive_folder_id)
        copied: list[str] = []
        for entry in files:
            if entry["type"] == "folder":
                sub = os.path.join(local_dir, entry["name"])
                child = self.sync_folder_down(entry["id"], sub)
                copied.extend(child["files"])
            else:
                target = self.download_file(entry["id"], os.path.join(local_dir, entry["name"]))
                copied.append(target)
        return {"folder_id": drive_folder_id, "local_dir": local_dir, "files": copied}

    def sync_folder_up(self, local_dir: str, drive_folder_id: str) -> dict:
        """Recursively push local_dir into a Drive folder."""
        import os
        if not os.path.isdir(local_dir):
            raise FileNotFoundError(f"Local directory not found: {local_dir}")
        uploaded: list[dict] = []
        for entry in sorted(os.listdir(local_dir)):
            full = os.path.join(local_dir, entry)
            if os.path.isdir(full):
                sub_id = self.create_folder(entry, parent_id=drive_folder_id)
                child = self.sync_folder_up(full, sub_id)
                uploaded.extend(child["files"])
            else:
                fid = self.upload_file(full, folder_id=drive_folder_id, name=entry)
                uploaded.append({"local": full, "drive_id": fid, "name": entry})
        return {"folder_id": drive_folder_id, "local_dir": local_dir, "files": uploaded}