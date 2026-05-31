"""FastAPI entrypoint for document scanning."""
from __future__ import annotations

import threading
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.gdrive_downloader import GDriveDownloader
from app.gdrive_extractor import GDriveLister
from app.process import ScanResult, scan_text
from detectors.regex import RegexDetectorConfig

app = FastAPI(title="GDPR Document Scanner", version="1.0.0")


class RegexConfigPayload(BaseModel):
    emails: bool = True
    phones: bool = True
    usernames: bool = True
    signatures: bool = True
    id_documents: bool = True
    ip_addresses: bool = True
    credit_cards: bool = True
    iban: bool = True
    ssn: bool = True
    dob: bool = True


class ScanTextRequest(BaseModel):
    text: str = Field(..., min_length=1)
    file_id: str = "inline-text"
    config: RegexConfigPayload | None = None


class ScanTextResponse(BaseModel):
    file_path: str
    findings: list[dict[str, Any]]
    has_pii: bool


class DriveWorkflowRequest(BaseModel):
    max_files: int | None = Field(default=None, ge=1)


class DriveWorkflowItem(BaseModel):
    file_id: str
    name: str
    mime_type: str
    has_pii: bool
    findings: list[dict[str, Any]]


class DriveWorkflowResponse(BaseModel):
    listed_files: int
    processed_files: int
    with_pii: int
    clean: int
    results: list[DriveWorkflowItem]


def _to_config(config: RegexConfigPayload | None) -> RegexDetectorConfig | None:
    if config is None:
        return None
    return RegexDetectorConfig(**config.model_dump())


def _to_response(result: ScanResult) -> ScanTextResponse:
    return ScanTextResponse(
        file_path=result.file_path,
        findings=result.findings,
        has_pii=result.has_pii,
    )


def run_drive_workflow(max_files: int | None = None) -> DriveWorkflowResponse:
    lister = GDriveLister()
    downloader = GDriveDownloader()

    results: list[DriveWorkflowItem] = []
    listed_files = 0

    for file_info in lister.list_files():
        if max_files is not None and len(results) >= max_files:
            break
        listed_files += 1

        text = downloader.download_and_extract(
            file_info["file_id"],
            file_info["mime_type"],
            file_info["name"],
        )
        scan_result = scan_text(text, file_info["file_id"])
        results.append(
            DriveWorkflowItem(
                file_id=file_info["file_id"],
                name=file_info["name"],
                mime_type=file_info["mime_type"],
                has_pii=scan_result.has_pii,
                findings=scan_result.findings,
            )
        )

    with_pii = sum(1 for item in results if item.has_pii)
    clean = len(results) - with_pii
    return DriveWorkflowResponse(
        listed_files=listed_files,
        processed_files=len(results),
        with_pii=with_pii,
        clean=clean,
        results=results,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scan/text", response_model=ScanTextResponse)
def scan_text_endpoint(payload: ScanTextRequest) -> ScanTextResponse:
    result = scan_text(payload.text, payload.file_id, _to_config(payload.config))
    return _to_response(result)


@app.post("/workflows/drive/scan")
def run_drive_workflow_endpoint(payload: DriveWorkflowRequest) -> dict:
    thread = threading.Thread(target=run_drive_workflow, args=(payload.max_files,), daemon=True)
    thread.start()
    return {"status": "triggered", "message": "Drive scan started in background."}
