"""
FastAPI entry point for the GDPR document scanner service.
Exposes workflow endpoints that trigger the Drive scanning pipeline.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import pubsub_v1
from pydantic import BaseModel, Field

from app.gdrive_extractor import GDriveLister
from app.process import ScanResult, scan_text
from detectors.regex import RegexDetectorConfig

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
