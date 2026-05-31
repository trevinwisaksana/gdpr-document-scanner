# API Endpoints

This project exposes one FastAPI service in `app/main.py`. The endpoints below are the public HTTP surface for the backend scanner.

## Health

| Method | Path | Purpose | Response |
|---|---|---|---|
| `GET` | `/health` | Basic liveness check for the API container. | `{"status":"ok"}` |

## Text Scanning

| Method | Path | Purpose | Response |
|---|---|---|---|
| `POST` | `/scan/text` | Scans already-extracted text for PII. Used by tests, direct callers, and the scanner pipeline. | `ScanTextResponse` with `file_path`, `findings`, `has_pii` |

Request body:

```json
{
  "text": "Contact user@example.com",
  "file_id": "invoice-1.txt",
  "config": {
    "emails": true,
    "phones": true
  }
}
```

## KPI Endpoints

These endpoints return live values from the Postgres `drive_files` table. They do not read from the history table.

| Method | Path | Purpose | Response |
|---|---|---|---|
| `GET` | `/kpis/total-files-registered` | Total rows in `drive_files`. | `{"value": <int>}` |
| `GET` | `/kpis/total-files-flagged` | Rows where `status_flag = 'flagged'`. | `{"value": <int>}` |
| `GET` | `/kpis/total-files-processed` | Rows whose `status_flag` is not still `not checked`. | `{"value": <int>}` |
| `GET` | `/kpis/percentage-files-flagged` | `flagged / processed * 100`. | `{"value": <float>}` |
| `GET` | `/kpis/owners` | Distinct non-empty owners from `drive_files`. | `{"owners": [<string>, ...]}` |
| `GET` | `/kpis/flagged-files-per-owner` | Flagged-file counts grouped by owner. | `{"items": [{"owner": "...", "flagged_files": <int>}, ...]}` |

## User File View

| Method | Path | Purpose | Response |
|---|---|---|---|
| `GET` | `/users/{user_id}/files` | Returns all flagged files owned by the requested user. | `FlaggedFilesResponse` with file metadata and finding counts |

This route depends on the seeded/demo user records in the SQLite app database and the `scanner.store.flagged_files_for_user()` query.

## Drive Workflow

| Method | Path | Purpose | Response |
|---|---|---|---|
| `POST` | `/workflows/drive/scan` | Lists Google Drive files and publishes each file to Pub/Sub for downstream extraction and scanning. | `{"files_queued": <int>, "failed": <int>, "status": "ok"}` |

## Notes

- The API is implemented in `app/main.py`.
- There is no auth layer in the current backend routes.
- `ALLOWED_ORIGINS` controls CORS.
- The KPI endpoints are live reads only; snapshot history is written separately after batch scans complete.
