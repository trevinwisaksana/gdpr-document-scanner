from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

from googleapiclient.http import MediaIoBaseDownload

from app.drive_mimes import GOOGLE_EXPORT, SUPPORTED_MIME, build_drive_service
from app.file_reader import extract_text


class GDriveDownloader:
    def __init__(self) -> None:
        self._service = build_drive_service()

    def download_and_extract(self, file_id: str, mime_type: str, file_name: str) -> str:
        buf = io.BytesIO()
        if mime_type in GOOGLE_EXPORT:
            export_mime, ext = GOOGLE_EXPORT[mime_type]
            request = self._service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            ext = SUPPORTED_MIME.get(mime_type, Path(file_name).suffix.lower())
            request = self._service.files().get_media(fileId=file_id)

        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        # Use delete=False so the file is closed before extract_text opens it (portable on all OSes)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(buf.getvalue())
                tmp.flush()
            return extract_text(tmp_path)
        finally:
            if tmp_path:
                os.unlink(tmp_path)
