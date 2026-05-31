# Run Staging Pipeline From Scratch

Scale the extraction consumer, wipe the DB, repopulate from Drive, and queue all files for scanning.

## DB connection capacity

Cloud SQL instance `drive-metadata-db` (db-f1-micro) has `max_connections=100`. Scanner consumer uses `ThreadedConnectionPool(minconn=1, maxconn=5)` per instance (flusher holds at most 1 connection at a time) — safe to run up to 8 instances. Do not increase beyond 8 without also raising `max_connections` via:
```bash
gcloud sql instances patch drive-metadata-db --database-flags=max_connections=<N> --project=summer-bond-461608-i5
```

## Key variables

```
PROJECT=summer-bond-461608-i5
REGION=us-central1
DB_HOST=104.197.163.23
DB_PASS='Prototype123!'
```

## Steps

### 1. Scale extraction consumer to 6–8 instances

```bash
gcloud run services update gdpr-extraction-consumer \
  --min-instances=6 --max-instances=8 \
  --project=summer-bond-461608-i5 --region=us-central1
```

### 2. Scale scanner consumer down (prevents DB connection exhaustion during reset)

Scanner uses `ThreadedConnectionPool(minconn=1, maxconn=5)` per instance. Scale to min=0 max=1 before touching the DB to avoid connection races during reset.

```bash
gcloud run services update gdpr-scanner-consumer \
  --min-instances=0 --max-instances=1 \
  --project=summer-bond-461608-i5 --region=us-central1
```

### 3. Truncate the drive_files table

```bash
PGPASSWORD='Prototype123!' psql -h 104.197.163.23 -U postgres -d postgres -c "TRUNCATE TABLE drive_files;"
```

### 4. Run the listing job (repopulates drive_files from Google Drive)

```bash
gcloud run jobs execute gdpr-listing-job \
  --project=summer-bond-461608-i5 --region=us-central1 --wait
```

### 5. Purge Pub/Sub subscriptions (discard stale messages from prior runs)

Without this, old scanner messages race against the fresh inserts and mark rows before extraction starts.

```bash
SEEK_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
gcloud pubsub subscriptions seek projects/summer-bond-461608-i5/subscriptions/gdpr-extraction-sub --time="$SEEK_TIME" --project=summer-bond-461608-i5
gcloud pubsub subscriptions seek projects/summer-bond-461608-i5/subscriptions/gdpr-scanner-sub --time="$SEEK_TIME" --project=summer-bond-461608-i5
```

### 6. Reset any status_flag rows left by the race

```bash
PGPASSWORD='Prototype123!' psql -h 104.197.163.23 -U postgres -d postgres \
  -c "UPDATE drive_files SET status_flag = 'not_checked' WHERE status_flag != 'not_checked';"
```

### 7. Scale scanner consumer back up

```bash
gcloud run services update gdpr-scanner-consumer \
  --min-instances=1 --max-instances=8 \
  --project=summer-bond-461608-i5 --region=us-central1
```

### 8. Trigger the extraction job (queues all not_checked files to Pub/Sub)

```bash
gcloud run jobs execute gdpr-extraction-job \
  --project=summer-bond-461608-i5 --region=us-central1 --wait
```

## Verify

### Progress check (run while pipeline is active)

```bash
PGPASSWORD='Prototype123!' psql -h 104.197.163.23 -U postgres -d postgres \
  -c "SELECT status_flag, count(*) FROM drive_files GROUP BY status_flag;"
```

All rows start as `not_checked`; they transition to `flagged` / `not_flagged` as the scanner processes them.

### Correctness check (run after all rows are scanned)

Ground truth is inferred from the file name: `internal_memo_*` files are clean (expected `not_flagged`); all others contain PII (expected `flagged`).

```bash
PGPASSWORD='Prototype123!' psql -h 104.197.163.23 -U postgres -d postgres -c "
SELECT
  SUM(CASE WHEN name NOT LIKE 'internal_memo_%' AND status_flag = 'flagged'     THEN 1 ELSE 0 END) AS tp,
  SUM(CASE WHEN name     LIKE 'internal_memo_%' AND status_flag = 'not_flagged' THEN 1 ELSE 0 END) AS tn,
  SUM(CASE WHEN name     LIKE 'internal_memo_%' AND status_flag = 'flagged'     THEN 1 ELSE 0 END) AS fp,
  SUM(CASE WHEN name NOT LIKE 'internal_memo_%' AND status_flag = 'not_flagged' THEN 1 ELSE 0 END) AS fn,
  COUNT(*) FILTER (WHERE status_flag IN ('flagged','not_flagged'))               AS total_scanned,
  COUNT(*) FILTER (WHERE status_flag = 'not_checked')                            AS pending
FROM drive_files;
"
```

Derived metrics:
- **Precision** = tp / (tp + fp)
- **Recall**    = tp / (tp + fn)
- **F1**        = 2 × precision × recall / (precision + recall)
