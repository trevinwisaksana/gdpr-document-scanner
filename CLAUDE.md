# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

Scan Google Drive files for GDPR personally identifiable information (PII). Files are listed from Drive, extracted to text, and scanned — results are stored in Postgres with a `status_flag` per file.

## Pipeline Architecture

```
Lister cronjob → Postgres → Extractor consumer → Pub/Sub → Scanner consumer → Postgres
```

1. **Lister** (`jobs/listing.py`) — Cloud Run Job on a schedule. Uses the service account to list all files in Google Drive (`SOURCE_FOLDER_ID=root`). Upserts file metadata into the `drive_files` Postgres table.

2. **Extractor consumer** (`services/extraction_consumer.py`) — Long-lived Cloud Run Service. Pulls file metadata messages from Pub/Sub (`PUBSUB_SUBSCRIPTION`), downloads and extracts text via `app/gdrive_downloader.py` + `app/file_reader.py`, then publishes `{file_id, name, text}` to the scanner Pub/Sub topic (`SCANNER_PUBSUB_TOPIC`).

3. **Scanner consumer** (`services/scanner_consumer.py`) — Long-lived Cloud Run Service. Pulls extracted-text messages from Pub/Sub, runs `scan_text()` from `app/process.py`, then updates `status_flag` (`flagged` / `not_flagged`) on the `drive_files` row in Postgres.

## Detection Pipeline (inside `app/process.py` → `scan_text()`)

Runs in order, each stage is a fallback for the previous:

1. **Regex** (`detectors/regex.py` → `detect_pii()`) — fast, deterministic, no external calls.
2. **Azure NER** (`app/NER.py` → `ner_inference()`) — called only when regex finds nothing. Uses Azure Language service (`NER_SUBSCRIPTION_KEY`). High-confidence findings (≥0.85) are kept directly; low-confidence ones are passed to LLM verify.
3. **LLM verify** (`app/llm_fallback.py` → `llm_verify_findings()`) — confirms low-confidence NER candidates via OpenRouter/Qwen.
4. **LLM detect** (`app/llm_fallback.py` → `llm_detect_pii()`) — called only when regex + NER both find nothing. Full PII scan via OpenRouter/Qwen.

## Supported File Types

`app/file_reader.py` handles: `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.xls`, `.csv`, `.txt`, `.html`, `.rtf`

## Environment Variables

| Variable | Description |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON (`credentials.json`) |
| `SOURCE_FOLDER_ID` | Google Drive folder ID to scan (`root` for all) |
| `DATABASE_URL` | Postgres connection string |
| `PUBSUB_SUBSCRIPTION` | Pub/Sub subscription for each consumer |
| `SCANNER_PUBSUB_TOPIC` | Pub/Sub topic extractor publishes to |
| `NER_SUBSCRIPTION_KEY` | Azure Language service key |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `OPENROUTER_MODEL` | Model to use (default: `qwen/qwen3-8b`) |
| `OPENROUTER_BASE_URL` | OpenRouter base URL |

## Key Files

| File | Purpose |
|---|---|
| `jobs/listing.py` | Lister cronjob entry point |
| `services/extraction_consumer.py` | Extractor Pub/Sub consumer |
| `services/scanner_consumer.py` | Scanner Pub/Sub consumer |
| `app/process.py` | `scan_text()` — core detection orchestration |
| `detectors/regex.py` | Regex-based PII detector |
| `app/NER.py` | Azure NER client |
| `app/llm_fallback.py` | OpenRouter/Qwen LLM detect + verify |
| `app/file_reader.py` | Text extraction for all file types |
| `app/gdrive_downloader.py` | Downloads files from Google Drive |
| `app/gdrive_extractor.py` | Lists files from Google Drive |
| `scanner/gdpr.py` | GDPR category definitions and metadata |

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run lister locally
python jobs/listing.py

# Run benchmark against test dataset
python benchmark.py --dataset ~/Desktop/test_dataset

# Run benchmark on a sample
python benchmark.py --sample 100
```

## Deployment

Cloud Run via Cloud Build (`cloudbuild.yaml`). Each service has its own Dockerfile:
- `Dockerfile` — main app
- `Dockerfile.job` — lister cronjob
- `Dockerfile.consumer` — extractor consumer
- `Dockerfile.scanner` — scanner consumer

## Notes

- Service account (`credentials.json`) has Drive read-only access — it cannot upload files.
- Python 3.13 required locally (the codebase uses `X | Y` union type syntax).
- `core/` folder has been deleted. Text extraction is in `app/file_reader.py`.
