# Postgres Schema

This project currently uses two live Postgres tables for the KPI and history flow:

- `drive_files`
- `kpi_snapshots`

The exact `drive_files` DDL is not defined in a migration file in this repo, so the structure below is the contract implied by the code that reads and writes it.

## `drive_files`

This is the operational table for Google Drive file metadata and scanner status.

| Column | Type | Purpose |
|---|---|---|
| `file_id` | text | Stable file identifier from Google Drive. Used as the lookup key in updates. |
| `name` | text | Human-readable file name. |
| `owner` | text | File owner identifier, currently treated as an email-like value. |
| `mime_type` | text | Drive MIME type used by the lister / downstream processing. |
| `google_created_at` | timestamp/text | Drive timestamp captured when the file is listed. |
| `is_deleted` | boolean | Whether Drive marks the file as trashed/deleted. |
| `last_seen_at` | timestamp | Updated when the scanner consumer processes the file. Used to detect reprocessing. |
| `status_flag` | text | Scanner state. Current code uses values like `flagged`, `not_flagged`, and `not checked`. |

### How the code uses it

- `app/gdrive_extractor.py` produces file metadata with `file_id`, `name`, `mime_type`, `modified_time`, `owner`, `deleted`, and `flag`.
- `services/scanner_consumer.py` updates `status_flag` and `last_seen_at` using `file_id`.
- `app/KPR_functions.py` reads KPI values directly from this table.
- The KPI endpoints in `app/main.py` are live reads from this table.

### Minimum indexes implied by the code

- `drive_files(file_id)` should be unique or primary key.
- `drive_files(owner)` is indexed in the scanner consumer.
- `drive_files(last_seen_at)` is useful for delta scans and KPI history, though not required by the current code.

## `kpi_snapshots`

This is the history table for point-in-time KPI snapshots taken after a batch scan completes.

| Column | Type | Purpose |
|---|---|---|
| `id` | bigserial | Primary key for each snapshot row. |
| `captured_at` | timestamptz | Time the snapshot was recorded. Defaults to `NOW()`. |
| `run_label` | text | Label for the run that created the snapshot, for example `full:<run_id>`. |
| `total_files_registered` | integer | Count of all rows in `drive_files`. |
| `total_files_flagged` | integer | Count of rows where `status_flag = 'flagged'`. |
| `total_files_processed` | integer | Count of rows that are no longer `not checked`. |
| `percentage_files_flagged` | numeric(7,2) | Flagged percentage at snapshot time. |
| `owners` | jsonb | Distinct owner list captured at snapshot time. |
| `flagged_files_per_owner` | jsonb | Owner breakdown of flagged-file counts captured at snapshot time. |

### Indexes

- `idx_kpi_snapshots_captured_at` on `(captured_at DESC)` for recent-first history views.

### How snapshots are written

- `scanner/scan.py` calls `record_kpi_snapshot()` after all files in a batch have been processed and the run is marked complete.
- `app/KPR_functions.py` creates the table if needed and inserts one row per completed batch.
- `kpi_smoke.py` can also write a snapshot manually when run as a smoke check.

## Relationship between the tables

- `drive_files` is the live operational table.
- `kpi_snapshots` is append-only history derived from `drive_files`.
- KPI API endpoints read from `drive_files`.
- Historical trend analysis reads from `kpi_snapshots`.
