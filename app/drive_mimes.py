from __future__ import annotations

import google_auth_httplib2
import httplib2
from google.auth import default
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive"]

# Google Workspace native types → (export MIME type, file extension)
GOOGLE_EXPORT: dict[str, tuple[str, str]] = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
}

# Regular Drive files → file extension
SUPPORTED_MIME: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "text/html": ".html",
    "application/rtf": ".rtf",
}


def build_drive_service():
    credentials, _ = default(scopes=SCOPES)
    http = google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http())
    return build("drive", "v3", http=http, cache_discovery=False)
