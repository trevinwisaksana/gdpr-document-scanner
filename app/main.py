"""
FastAPI entry point for the GDPR document scanner service.
Exposes workflow endpoints that trigger the Drive scanning pipeline.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import pubsub_v1
from pydantic import BaseModel, Field

from app.gdrive_extractor import GDriveLister
from app.KPR_functions import (
    flagged_files_per_owner,
    list_all_owners,
    percentage_files_flagged,
    percentage_files_flagged_over_time,
    total_files_flagged_over_time,
    total_files_over_time,
    total_files_flagged,
    total_files_processed,
    total_files_registered,
)
from app.process import ScanResult, scan_text
from detectors.regex import RegexDetectorConfig
import scanner.store as store

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

_publisher: pubsub_v1.PublisherClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _publisher
    _publisher = pubsub_v1.PublisherClient()
    logger.info(json.dumps({"event": "api_startup", "service": "gdpr-document-scanner"}))
    yield
    if _publisher:
        _publisher.close()
    logger.info(json.dumps({"event": "api_shutdown", "service": "gdpr-document-scanner"}))


app = FastAPI(title="GDPR Document Scanner", version="1.0.0", lifespan=lifespan)

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


class KPITrendRegisteredItem(BaseModel):
    captured_at: Any
    total_files_registered: int


class KPITrendRegisteredResponse(BaseModel):
    items: list[KPITrendRegisteredItem]


class KPITrendFlaggedItem(BaseModel):
    captured_at: Any
    total_files_flagged: int


class KPITrendFlaggedResponse(BaseModel):
    items: list[KPITrendFlaggedItem]


class KPITrendPercentageItem(BaseModel):
    captured_at: Any
    percentage_files_flagged: float


class KPITrendPercentageResponse(BaseModel):
    items: list[KPITrendPercentageItem]


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


@app.get("/kpis/total-files-registered-over-time", response_model=KPITrendRegisteredResponse)
def kpi_total_files_registered_over_time() -> KPITrendRegisteredResponse:
    return KPITrendRegisteredResponse(
        items=[KPITrendRegisteredItem(**row) for row in total_files_over_time()]
    )


@app.get("/kpis/total-files-flagged-over-time", response_model=KPITrendFlaggedResponse)
def kpi_total_files_flagged_over_time() -> KPITrendFlaggedResponse:
    return KPITrendFlaggedResponse(
        items=[KPITrendFlaggedItem(**row) for row in total_files_flagged_over_time()]
    )


@app.get("/kpis/percentage-files-flagged-over-time", response_model=KPITrendPercentageResponse)
def kpi_percentage_files_flagged_over_time() -> KPITrendPercentageResponse:
    return KPITrendPercentageResponse(
        items=[
            KPITrendPercentageItem(**row)
            for row in percentage_files_flagged_over_time()
        ]
    )


@app.get("/users/{user_id}/files", response_model=FlaggedFilesResponse)
def list_flagged_files(user_id: str) -> FlaggedFilesResponse:
    """Return all flagged files (files with PII findings) that belong to the given user."""
    store.init_db()
    user = store.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    rows = store.flagged_files_for_user(user_id)
    files = [
        FlaggedFile(
            id=row["id"],
            path=row["path"],
            source_type=row["source_type"],
            size_bytes=row["size_bytes"],
            last_modified=row["last_modified"],
            last_scanned_at=row["last_scanned_at"],
            n_findings=row["n_findings"],
            finding_categories=row["categories"].split(",") if row["categories"] else [],
        )
        for row in rows
    ]
    return FlaggedFilesResponse(user_id=user_id, total=len(files), files=files)


@app.patch("/findings/{finding_id}/status", response_model=FindingActionResponse)
def update_finding_status(finding_id: str, payload: FindingActionRequest) -> FindingActionResponse:
    store.init_db()
    status = _ACTION_TO_STATUS[payload.action]
    updated = store.set_finding_status(finding_id, status)
    if not updated:
        raise HTTPException(status_code=404, detail="finding not found")
    return FindingActionResponse(finding_id=finding_id, status=status)


@app.post("/workflows/drive/scan", response_model=DriveWorkflowResponse)
def trigger_drive_scan() -> DriveWorkflowResponse:
    """List all accessible Drive files and enqueue each for extraction and PII scanning."""
    topic = os.environ.get("PUBSUB_TOPIC")
    if not topic:
        raise HTTPException(status_code=500, detail="PUBSUB_TOPIC not configured")
    if _publisher is None:
        raise HTTPException(status_code=503, detail="publisher not ready")

    lister = GDriveLister()
    queued = 0
    failed = 0

    for file in lister.list_files():
        try:
            _publisher.publish(topic, json.dumps(file).encode()).result()
            queued += 1
            logger.info("queued file_id=%s name=%r", file["file_id"], file["name"])
        except Exception as exc:
            logger.error("publish failed file_id=%s error=%s", file["file_id"], exc)
            failed += 1

    logger.info("scan trigger complete queued=%d failed=%d", queued, failed)
    return DriveWorkflowResponse(files_queued=queued, failed=failed, status="ok")
