"""
FastAPI entry point for the GDPR document scanner service.
Exposes workflow endpoints that trigger the Drive scanning pipeline.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.drive.extractor import GDriveLister
from app.db.kpis import (
    flagged_files_for_owner,
    flagged_files_per_owner,
    list_all_owners,
    owner_exists,
    percentage_files_flagged,
    set_file_user_decision,
    total_files_flagged,
    total_files_processed,
    total_files_registered,
)
from app.process import ScanResult, scan_text
from detectors.regex import RegexDetectorConfig

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="GDPR Document Scanner", version="1.0.0")

allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins != ["*"] else ["*"],
    allow_credentials=allowed_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class DriveWorkflowResponse(BaseModel):
    files_queued: int
    failed: int
    status: str


class FlaggedFile(BaseModel):
    id: str
    path: str
    source_type: str
    size_bytes: int
    last_modified: float
    last_scanned_at: float | None
    n_findings: int
    finding_categories: list[str]


class FlaggedFilesResponse(BaseModel):
    user_id: str
    total: int
    files: list[FlaggedFile]


class KPIValueResponse(BaseModel):
    value: int | float


class KPIOwnersResponse(BaseModel):
    owners: list[str]


class KPIFlaggedByOwnerItem(BaseModel):
    owner: str
    flagged_files: int


class KPIFlaggedByOwnerResponse(BaseModel):
    items: list[KPIFlaggedByOwnerItem]


class FindingActionRequest(BaseModel):
    action: Literal["confirm_delete", "keep", "false_positive"]


class FindingActionResponse(BaseModel):
    finding_id: str
    status: str


_ACTION_TO_STATUS: dict[str, str] = {
    "confirm_delete": "delete",
    "keep": "keep",
    "false_positive": "false_positive",
}


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


@app.get("/health")
@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scan/text", response_model=ScanTextResponse)
def scan_text_endpoint(payload: ScanTextRequest) -> ScanTextResponse:
    result = scan_text(payload.text, payload.file_id, _to_config(payload.config))
    return _to_response(result)


@app.get("/kpis/total-files-registered", response_model=KPIValueResponse)
def kpi_total_files_registered() -> KPIValueResponse:
    return KPIValueResponse(value=total_files_registered())


@app.get("/kpis/total-files-flagged", response_model=KPIValueResponse)
def kpi_total_files_flagged() -> KPIValueResponse:
    return KPIValueResponse(value=total_files_flagged())


@app.get("/kpis/total-files-processed", response_model=KPIValueResponse)
def kpi_total_files_processed() -> KPIValueResponse:
    return KPIValueResponse(value=total_files_processed())


@app.get("/kpis/percentage-files-flagged", response_model=KPIValueResponse)
def kpi_percentage_files_flagged() -> KPIValueResponse:
    return KPIValueResponse(value=percentage_files_flagged())


@app.get("/kpis/owners", response_model=KPIOwnersResponse)
def kpi_owners() -> KPIOwnersResponse:
    return KPIOwnersResponse(owners=list_all_owners())


@app.get("/kpis/flagged-files-per-owner", response_model=KPIFlaggedByOwnerResponse)
def kpi_flagged_files_per_owner() -> KPIFlaggedByOwnerResponse:
    return KPIFlaggedByOwnerResponse(
        items=[KPIFlaggedByOwnerItem(**row) for row in flagged_files_per_owner()]
    )


def _to_epoch(val: object) -> float:
    """Convert a datetime object or ISO string to a Unix timestamp."""
    if val is None:
        return 0.0
    if hasattr(val, "timestamp"):
        return val.timestamp()
    try:
        from datetime import datetime, timezone
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return 0.0


@app.get("/users/{user_id}/files", response_model=FlaggedFilesResponse)
def list_flagged_files(user_id: str) -> FlaggedFilesResponse:
    """Return all flagged Drive files that belong to the given owner (email)."""
    if not owner_exists(user_id):
        raise HTTPException(status_code=404, detail="user not found")

    rows = flagged_files_for_owner(user_id)
    files = [
        FlaggedFile(
            id=row["file_id"],
            path=row["name"],
            source_type="gdrive",
            size_bytes=0,
            last_modified=_to_epoch(row["google_created_at"]),
            last_scanned_at=_to_epoch(row["last_seen_at"]) or None,
            n_findings=1,
            finding_categories=[row["pii_category"]] if row["pii_category"] else [],
        )
        for row in rows
    ]
    return FlaggedFilesResponse(user_id=user_id, total=len(files), files=files)


@app.patch("/files/{file_id}/status", response_model=FindingActionResponse)
def update_file_status(file_id: str, payload: FindingActionRequest) -> FindingActionResponse:
    status = _ACTION_TO_STATUS[payload.action]
    updated = set_file_user_decision(file_id, status)
    if not updated:
        raise HTTPException(status_code=404, detail="file not found")
    return FindingActionResponse(finding_id=file_id, status=status)


@app.post("/workflows/drive/scan", response_model=DriveWorkflowResponse)
def trigger_drive_scan() -> DriveWorkflowResponse:
    """List all accessible Drive files and upsert them into Postgres."""
    lister = GDriveLister()
    count = lister.run()
    logger.info("drive scan complete files=%d", count)
    return DriveWorkflowResponse(files_queued=count, failed=0, status="ok")
