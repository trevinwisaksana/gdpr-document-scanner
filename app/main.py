"""FastAPI entry point for the GDPR scanner Cloud Run service."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup")
    yield
    logger.info("shutdown")


app = FastAPI(title="GDPR Document Scanner", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/workflows/drive/scan")
def trigger_drive_scan():
    """List all accessible Google Drive files and enqueue them for scanning."""
    try:
        from app.gdrive_extractor import GDriveLister
        lister = GDriveLister()
        files_queued = lister.run()
        logger.info("drive scan triggered files_queued=%d", files_queued)
        return {"status": "triggered", "files_queued": files_queued}
    except Exception as exc:
        logger.error("drive scan failed error=%s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
