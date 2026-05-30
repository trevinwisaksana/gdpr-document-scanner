"""Dispatcher service — triggered by Cloud Scheduler.

POST /dispatch  lists all files in the configured GCS bucket and publishes
                one Pub/Sub message per file to the scan-jobs topic.
GET  /health    liveness probe for Cloud Run.
"""
from __future__ import annotations

import json
import logging
import os

from fastapi import FastAPI, HTTPException
from google.cloud import pubsub_v1, storage

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="GDPR Scanner Dispatcher")

_PROJECT_ID  = os.environ["GCP_PROJECT_ID"]
_BUCKET_NAME = os.environ["GCS_BUCKET_NAME"]
_TOPIC_ID    = os.environ["PUBSUB_TOPIC_ID"]
_FILE_PREFIX = os.getenv("GCS_FILE_PREFIX", "")

_publisher  = pubsub_v1.PublisherClient()
_topic_path = _publisher.topic_path(_PROJECT_ID, _TOPIC_ID)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/dispatch")
def dispatch() -> dict:
    """List bucket contents and enqueue one scan job per file."""
    gcs = storage.Client()
    blobs = list(gcs.list_blobs(_BUCKET_NAME, prefix=_FILE_PREFIX or None))

    if not blobs:
        logger.info("dispatch: no files found", extra={"bucket": _BUCKET_NAME, "prefix": _FILE_PREFIX})
        return {"queued": 0}

    futures = [
        _publisher.publish(
            _topic_path,
            json.dumps({"bucket": _BUCKET_NAME, "object": blob.name}).encode(),
        )
        for blob in blobs
    ]

    errors: list[str] = []
    for future in futures:
        try:
            future.result()
        except Exception as exc:
            errors.append(str(exc))

    if errors:
        logger.error("dispatch: publish failures", extra={"count": len(errors), "sample": errors[:3]})
        raise HTTPException(status_code=500, detail=f"{len(errors)} of {len(blobs)} messages failed to publish")

    logger.info("dispatch: complete", extra={"queued": len(blobs)})
    return {"queued": len(blobs)}
