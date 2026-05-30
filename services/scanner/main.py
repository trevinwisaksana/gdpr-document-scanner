"""Scanner worker — receives Pub/Sub push messages, scans each GCS file for PII.

Pub/Sub push envelope:
  {"message": {"data": "<base64-encoded JSON>", ...}, "subscription": "..."}

Message data JSON:
  {"bucket": "my-bucket", "object": "path/to/file.pdf"}

Return codes:
  200 — scan complete (Pub/Sub acks the message)
  400 — malformed message (Pub/Sub will NOT retry; routes to dead-letter topic)
  500 — transient failure (Pub/Sub retries with backoff)
"""
from __future__ import annotations

import base64
import json
import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from google.cloud import storage

from app.process import process_file

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="GDPR Scanner Worker")

_gcs = storage.Client()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/scan")
async def scan(request: Request) -> dict:
    """Decode a Pub/Sub push message and scan the referenced GCS file."""
    body = await request.json()

    try:
        raw = base64.b64decode(body["message"]["data"]).decode()
        data = json.loads(raw)
        bucket_name: str = data["bucket"]
        object_name: str = data["object"]
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid message: {exc}")

    suffix = Path(object_name).suffix.lower()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        _gcs.bucket(bucket_name).blob(object_name).download_to_filename(str(tmp_path))
        result = process_file(tmp_path)
    except Exception as exc:
        logger.exception("Scan failed", extra={"object": object_name})
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)

    logger.info(
        "Scan complete",
        extra={"object": object_name, "has_pii": result.has_pii, "findings": len(result.findings)},
    )
    return {
        "object": object_name,
        "has_pii": result.has_pii,
        "findings": len(result.findings),
    }
