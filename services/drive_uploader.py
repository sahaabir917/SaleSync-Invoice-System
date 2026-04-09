"""
Google Drive upload service.
Supports two auth methods (tried in order):
  1. OAuth 2.0 token file  (set up via the "Connect Google Drive" button in the UI)
  2. Service Account JSON  (advanced / server deployments)
"""
import io
import json
import logging
import os

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_INVOICES_FOLDER_NAME = "Invoices"


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

def get_status(oauth_token_file: str, sa_file: str, folder_id: str) -> dict:
    """Return current Drive connection status."""
    if os.path.isfile(oauth_token_file):
        try:
            creds = _load_oauth_creds(oauth_token_file)
            if creds and creds.valid:
                return {"connected": True, "method": "oauth"}
            # Try refresh
            creds = _refresh_oauth(creds, oauth_token_file)
            if creds and creds.valid:
                return {"connected": True, "method": "oauth"}
        except Exception as e:
            logger.warning("OAuth token invalid: %s", e)
    if os.path.isfile(sa_file) and folder_id:
        return {"connected": True, "method": "service_account"}
    return {"connected": False, "method": None}


def is_configured(oauth_token_file: str, sa_file: str, folder_id: str) -> bool:
    return get_status(oauth_token_file, sa_file, folder_id)["connected"]


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def build_oauth_flow(client_id: str, client_secret: str, redirect_uri: str):
    from google_auth_oauthlib.flow import Flow
    return Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": [redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=_SCOPES,
        redirect_uri=redirect_uri,
    )


def save_oauth_token(creds, token_file: str):
    os.makedirs(os.path.dirname(token_file) or ".", exist_ok=True)
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or _SCOPES),
    }
    with open(token_file, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("OAuth token saved to %s", token_file)


def _load_oauth_creds(token_file: str):
    from google.oauth2.credentials import Credentials
    with open(token_file) as f:
        data = json.load(f)
    return Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes", _SCOPES),
    )


def _refresh_oauth(creds, token_file: str):
    from google.auth.transport.requests import Request
    try:
        creds.refresh(Request())
        save_oauth_token(creds, token_file)
    except Exception as e:
        logger.error("OAuth refresh failed: %s", e)
    return creds


def disconnect_oauth(token_file: str):
    if os.path.isfile(token_file):
        os.remove(token_file)
        logger.info("OAuth token removed")


# ---------------------------------------------------------------------------
# Drive service builder
# ---------------------------------------------------------------------------

def _build_service(oauth_token_file: str, sa_file: str):
    from googleapiclient.discovery import build

    # Prefer OAuth token
    if os.path.isfile(oauth_token_file):
        creds = _load_oauth_creds(oauth_token_file)
        if not creds.valid and creds.refresh_token:
            creds = _refresh_oauth(creds, oauth_token_file)
        return build("drive", "v3", credentials=creds)

    # Fall back to service account
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(sa_file, scopes=_SCOPES)
    return build("drive", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Folder helpers
# ---------------------------------------------------------------------------

def _get_or_create_folder(service, folder_id: str) -> str:
    """Return folder_id if provided, otherwise find or create 'Invoices' folder."""
    if folder_id:
        return folder_id

    # Search for existing "Invoices" folder
    q = f"name='{_INVOICES_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=q, fields="files(id,name)").execute()
    files = results.get("files", [])
    if files:
        fid = files[0]["id"]
        logger.info("Found existing Drive folder '%s' (id=%s)", _INVOICES_FOLDER_NAME, fid)
        return fid

    # Create the folder
    meta = {"name": _INVOICES_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}
    folder = service.files().create(body=meta, fields="id").execute()
    fid = folder["id"]
    logger.info("Created Drive folder '%s' (id=%s)", _INVOICES_FOLDER_NAME, fid)
    return fid


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_pdf(
    pdf_bytes: bytes,
    filename: str,
    oauth_token_file: str,
    sa_file: str,
    folder_id: str,
) -> dict:
    """Upload pdf_bytes to Google Drive. Returns {file_id, drive_url, filename}."""
    from googleapiclient.http import MediaIoBaseUpload

    service = _build_service(oauth_token_file, sa_file)
    target_folder = _get_or_create_folder(service, folder_id)

    file_metadata = {
        "name": filename,
        "parents": [target_folder],
        "mimeType": "application/pdf",
    }
    media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf", resumable=False)
    result = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id,webViewLink,name",
    ).execute()

    logger.info("Uploaded '%s' to Drive folder %s (file id=%s)", filename, target_folder, result.get("id"))
    return {
        "file_id": result.get("id"),
        "drive_url": result.get("webViewLink"),
        "filename": result.get("name"),
    }
