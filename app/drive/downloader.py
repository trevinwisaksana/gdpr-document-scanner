from __future__ import annotations

import base64
import io
import os
import tempfile
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseDownload
import requests

from app.drive.mimes import GOOGLE_EXPORT, SUPPORTED_MIME, build_drive_service
from app.extraction.reader import extract_text


OCR_PDF_MIN_CHARS = int(os.getenv("GDRIVE_OCR_PDF_MIN_CHARS", "80"))
OCR_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "image/bmp",
    "image/webp",
}
VISION_SCOPES = ["https://www.googleapis.com/auth/cloud-vision"]
VISION_API_URL = "https://vision.googleapis.com/v1/images:annotate"
VIDEO_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
VIDEO_API_URL = "https://videointelligence.googleapis.com/v1/videos:annotate"
VIDEO_OPERATION_URL = "https://videointelligence.googleapis.com/v1"
VIDEO_TRANSCRIPTION_TIMEOUT_SECONDS = int(os.getenv("VIDEO_TRANSCRIPTION_TIMEOUT_SECONDS", "600"))
VIDEO_TRANSCRIPTION_POLL_SECONDS = float(os.getenv("VIDEO_TRANSCRIPTION_POLL_SECONDS", "2"))
VIDEO_LANGUAGE_CODE = os.getenv("VIDEO_LANGUAGE_CODE", "en-US")


class GDriveDownloader:
    def __init__(self) -> None:
        self._service = build_drive_service()
        self._vision_credentials = None
        self._video_credentials = None

    def download_and_extract(self, file_id: str, mime_type: str, file_name: str) -> str:
        ext, file_bytes = self._download_bytes(file_id, mime_type, file_name)

        if mime_type in OCR_IMAGE_MIME_TYPES:
            return self._ocr_image_bytes(file_bytes, file_name)
        if mime_type.startswith("video/"):
            return self._transcribe_video_bytes(file_bytes, file_name)

        # Use delete=False so the file is closed before extract_text opens it (portable on all OSes)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(file_bytes)
                tmp.flush()
            try:
                local_text = extract_text(tmp_path)
            except Exception:
                if mime_type != "application/pdf":
                    raise
                local_text = ""
            if mime_type == "application/pdf" and self._should_use_pdf_ocr(local_text):
                ocr_text = self._ocr_pdf_bytes(file_bytes, file_name)
                if ocr_text.strip():
                    return ocr_text
            return local_text
        finally:
            if tmp_path:
                os.unlink(tmp_path)

    def _download_bytes(self, file_id: str, mime_type: str, file_name: str) -> tuple[str, bytes]:
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
        return ext, buf.getvalue()

    def _should_use_pdf_ocr(self, text: str) -> bool:
        return len(text.strip()) < OCR_PDF_MIN_CHARS

    def _get_vision_client(self):
        if self._vision_credentials is None:
            self._vision_credentials = service_account.Credentials.from_service_account_file(
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
                scopes=VISION_SCOPES,
            )
        if not self._vision_credentials.valid or not self._vision_credentials.token:
            self._vision_credentials.refresh(Request())
        return self._vision_credentials

    def _get_video_credentials(self):
        if self._video_credentials is None:
            self._video_credentials = service_account.Credentials.from_service_account_file(
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
                scopes=VIDEO_SCOPES,
            )
        if not self._video_credentials.valid or not self._video_credentials.token:
            self._video_credentials.refresh(Request())
        return self._video_credentials

    def _ocr_image_bytes(self, file_bytes: bytes, file_name: str) -> str:
        credentials = self._get_vision_client()
        payload = {
            "requests": [
                {
                    "image": {"content": base64.b64encode(file_bytes).decode("ascii")},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                }
            ]
        }
        response = requests.post(
            VISION_API_URL,
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        body = response.json()
        result = (body.get("responses") or [{}])[0]
        error = result.get("error")
        if error:
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise RuntimeError(f"Vision OCR failed for {file_name}: {message}")
        return self._vision_response_to_text(result, file_name)

    def _ocr_pdf_bytes(self, file_bytes: bytes, file_name: str) -> str:
        import pymupdf

        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        page_texts: list[str] = []
        try:
            for page in doc:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                page_text = self._ocr_image_bytes(pix.tobytes("png"), file_name)
                if page_text.strip():
                    page_texts.append(page_text.strip())
        finally:
            doc.close()
        return "\n\n".join(page_texts)

    def _transcribe_video_bytes(self, file_bytes: bytes, file_name: str) -> str:
        credentials = self._get_video_credentials()
        payload = {
            "inputContent": base64.b64encode(file_bytes).decode("ascii"),
            "features": ["SPEECH_TRANSCRIPTION", "TEXT_DETECTION"],
            "videoContext": {
                "speechTranscriptionConfig": {
                    "languageCode": VIDEO_LANGUAGE_CODE,
                    "enableAutomaticPunctuation": True,
                }
            },
        }
        response = requests.post(
            VIDEO_API_URL,
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        operation = response.json()
        operation_name = operation.get("name")
        if not operation_name:
            raise RuntimeError(f"Video transcription failed for {file_name}: missing operation name")

        deadline = time.monotonic() + VIDEO_TRANSCRIPTION_TIMEOUT_SECONDS
        while not operation.get("done"):
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Video transcription timed out for {file_name}")
            time.sleep(VIDEO_TRANSCRIPTION_POLL_SECONDS)
            poll = requests.get(
                f"{VIDEO_OPERATION_URL}/{operation_name}",
                headers={"Authorization": f"Bearer {credentials.token}"},
                timeout=30,
            )
            poll.raise_for_status()
            operation = poll.json()
            if operation.get("error"):
                raise RuntimeError(f"Video transcription failed for {file_name}: {operation['error']}")

        return self._extract_video_text(operation, file_name)

    @staticmethod
    def _extract_video_text(operation: dict, file_name: str) -> str:
        response = operation.get("response") or {}
        annotation_results = response.get("annotationResults") or []
        parts: list[str] = []

        for annotation in annotation_results:
            for transcription in annotation.get("speechTranscriptions", []) or []:
                alternatives = transcription.get("alternatives", []) or []
                if alternatives:
                    transcript = (alternatives[0].get("transcript") or "").strip()
                    if transcript:
                        parts.append(transcript)
            for text_annotation in annotation.get("textAnnotations", []) or []:
                text = (text_annotation.get("text") or "").strip()
                if text:
                    parts.append(text)

        if not parts:
            return ""
        # Keep the output stable for downstream PII scanning.
        deduped: list[str] = []
        seen: set[str] = set()
        for part in parts:
            if part not in seen:
                seen.add(part)
                deduped.append(part)
        return "\n\n".join(deduped)

    @staticmethod
    def _vision_response_to_text(response: dict, file_name: str) -> str:
        annotation = response.get("fullTextAnnotation") or {}
        text = annotation.get("text", "")
        if text:
            return text

        texts = response.get("textAnnotations") or []
        if texts:
            first = texts[0]
            return first.get("description", "")
        return ""
