"""
Upload the newly generated varied dataset to Google Drive.
Mirrors the local test_dataset folder structure into Drive.
Run: python upload_varied_data.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

TEST_DATASET_DIR = Path(os.path.expanduser("~/Desktop/test_dataset"))
CLIENT_SECRETS_FILE = Path(__file__).parent / "client_secrets.json"
TOKEN_FILE = Path(__file__).parent / "drive_token.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]

# Only upload files with these prefixes (the newly generated ones)
NEW_PREFIXES = ("regex_record_", "ner_record_", "ner_staff_", "subtle_record_")


def get_drive_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_FILE), SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=True)
        TOKEN_FILE.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, name: str, parent_id: str, cache: dict) -> str:
    key = (name, parent_id)
    if key in cache:
        return cache[key]
    # Check if it already exists
    resp = service.files().list(
        q=f"name='{name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)",
        pageSize=1,
    ).execute()
    files = resp.get("files", [])
    if files:
        folder_id = files[0]["id"]
    else:
        meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
        folder_id = service.files().create(body=meta, fields="id").execute()["id"]
        print(f"  Created folder: {name}")
    cache[key] = folder_id
    return folder_id


MIME_MAP = {
    ".txt":  "text/plain",
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv":  "text/csv",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def upload_file(service, folder_id: str, local_path: Path) -> None:
    mime = MIME_MAP.get(local_path.suffix.lower(), "application/octet-stream")
    meta = {"name": local_path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(local_path), mimetype=mime, resumable=False)
    service.files().create(body=meta, media_body=media, fields="id").execute()


def main():
    print("Connecting to Google Drive...")
    service = get_drive_service()

    # Find the Drive root (My Drive) id
    root_id = service.files().get(fileId="root", fields="id").execute()["id"]
    folder_cache: dict = {}

    # Collect new files to upload
    new_files = [
        p for p in sorted(TEST_DATASET_DIR.rglob("*"))
        if p.is_file() and p.name.startswith(NEW_PREFIXES)
    ]
    print(f"Found {len(new_files)} new files to upload.\n")

    for i, local_path in enumerate(new_files, 1):
        rel = local_path.relative_to(TEST_DATASET_DIR)
        parts = rel.parts  # e.g. ('HR', 'Onboarding', 'ner_record_001_...txt')

        # Build folder path in Drive
        parent = root_id
        for part in parts[:-1]:
            parent = get_or_create_folder(service, part, parent, folder_cache)

        upload_file(service, parent, local_path)
        print(f"  [{i}/{len(new_files)}] {rel}")

    print(f"\nDone. Uploaded {len(new_files)} files.")


if __name__ == "__main__":
    main()
