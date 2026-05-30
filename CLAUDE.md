# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

Build a GDPR data scanner that detects personally identifiable information (PII) in files and documents stored in blob storage (e.g., Google Cloud Storage). The service is deployed as a FastAPI app on Google Cloud Run.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# Run with environment variables
PORT=8080 ALLOWED_ORIGINS=* uvicorn app.main:app --reload
```

## Architecture

**Runtime**: FastAPI on Python 3.12, containerized via Docker, deployed to Cloud Run via Cloud Build (`cloudbuild.yaml`).

**Entry point**: `app/main.py` — sets up FastAPI with CORS, structured JSON logging, and a lifespan context manager for startup/shutdown hooks.

**Deployment**: `cloudbuild.yaml` builds the Docker image, pushes to Artifact Registry (`us-central1`), and deploys to Cloud Run using commit SHA as the image tag. The service is unauthenticated (`--allow-unauthenticated`).

**Environment variables** (see `.env.example`):
- `PORT` — defaults to `8080`
- `ALLOWED_ORIGINS` — comma-separated CORS origins, defaults to `*`

## Key Design Constraints

- The app runs as a non-root `appuser` inside the container (security hardening in `Dockerfile`).
- Logging is structured JSON to stdout, compatible with Cloud Logging.
- Document/blob scanning logic should integrate with the lifespan context (startup) for any clients that need initialization (e.g., GCS client, PII detection models).
