"""
Google Drive Auth
=================

Two auth modes:

  1. Service account (preferred for server-side / Colab use):
     - GOOGLE_DRIVE_CREDENTIALS_JSON points at a service-account JSON file.

  2. OAuth user flow (for individual user Drive access):
     - GOOGLE_DRIVE_OAUTH_TOKEN points at a token JSON containing a refresh
       token (the result of an `InstalledAppFlow` run).

The cached token is written to predictor/backend/.cache/drive_token.json so
subsequent boots don't need to re-run the user flow.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Scopes:
#   drive.file     — read/write files the app created or that were opened with it
#   drive.readonly — list/read user files (needed for browse + import)
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly",
]

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = _BACKEND_ROOT / ".cache"
TOKEN_CACHE_PATH = CACHE_DIR / "drive_token.json"


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _service_account_credentials():
    sa_path = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_JSON")
    if not sa_path or not Path(sa_path).is_file():
        return None
    try:
        from google.oauth2 import service_account
    except ImportError:
        raise RuntimeError(
            "google-auth is not installed. Run: pip install google-auth google-api-python-client"
        )
    return service_account.Credentials.from_service_account_file(
        sa_path, scopes=DEFAULT_SCOPES,
    )


def _oauth_credentials():
    """Build user OAuth credentials from a cached refresh-token JSON.

    The token JSON must include client_id, client_secret, refresh_token, and
    token_uri (the standard fields produced by `Credentials.to_json()`).
    """
    token_path = os.environ.get("GOOGLE_DRIVE_OAUTH_TOKEN") or (
        str(TOKEN_CACHE_PATH) if TOKEN_CACHE_PATH.exists() else None
    )
    if not token_path or not Path(token_path).is_file():
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        raise RuntimeError(
            "google-auth is not installed. Run: pip install google-auth google-auth-oauthlib"
        )

    creds = Credentials.from_authorized_user_file(token_path, DEFAULT_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _ensure_cache_dir()
            TOKEN_CACHE_PATH.write_text(creds.to_json())
        except Exception as exc:
            logger.warning("Failed to refresh Drive OAuth token: %s", exc)
            return None
    return creds


def get_credentials():
    """Return the best available Drive credentials, or None."""
    sa = _service_account_credentials()
    if sa is not None:
        return sa
    return _oauth_credentials()


def is_authenticated() -> bool:
    try:
        return get_credentials() is not None
    except Exception:
        return False


def auth_status() -> dict[str, Any]:
    sa_path = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_JSON")
    oauth_path = os.environ.get("GOOGLE_DRIVE_OAUTH_TOKEN")
    has_cached = TOKEN_CACHE_PATH.exists()
    return {
        "authenticated":            is_authenticated(),
        "service_account_path":     sa_path,
        "service_account_present":  bool(sa_path and Path(sa_path).is_file()),
        "oauth_token_path":         oauth_path,
        "oauth_token_present":      bool(oauth_path and Path(oauth_path).is_file()),
        "cached_token_present":     has_cached,
        "scopes":                   DEFAULT_SCOPES,
    }


def build_oauth_flow(client_secrets_path: str, redirect_uri: str | None = None):
    """Build an InstalledAppFlow for the OAuth user flow.

    Caller is responsible for completing the flow (e.g. opening a browser to
    `flow.authorization_url()` and exchanging the returned code).
    """
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise RuntimeError(
            "google-auth-oauthlib is not installed. "
            "Run: pip install google-auth-oauthlib"
        )
    flow = Flow.from_client_secrets_file(
        client_secrets_path, scopes=DEFAULT_SCOPES,
    )
    if redirect_uri:
        flow.redirect_uri = redirect_uri
    return flow


def save_oauth_token(creds_json: str | dict) -> Path:
    """Persist an OAuth token (as returned by Credentials.to_json()) to the cache."""
    _ensure_cache_dir()
    payload = creds_json if isinstance(creds_json, str) else json.dumps(creds_json)
    TOKEN_CACHE_PATH.write_text(payload)
    return TOKEN_CACHE_PATH
