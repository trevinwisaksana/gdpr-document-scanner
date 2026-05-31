# Run Staging Pipeline From Scratch

Scale the extraction consumer, wipe the DB, repopulate from Drive, and queue all files for scanning.

## DB connection capacity

Cloud SQL instance `drive-metadata-db` (db-f1-micro) has `max_connections=200`. Scanner consumer uses `ThreadedConnectionPool(minconn=1, maxconn=5)` per instance — safe to run up to 20 instances (20 × 5 = 100 connections, well within 200).

## Key variables

```
PROJECT=summer-bond-461608-i5
REGION=us-central1
DB_HOST=104.197.163.23
DB_PASS='Prototype123!'
```

## Steps

### 1. Truncate the drive_files table

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

### 7. Trigger the extraction job (queues all not_checked files to Pub/Sub)

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

Ground truth is inferred from file name: `internal_memo_*` = clean (expected `not_flagged`); everything else = PII (expected `flagged`).

```bash
PGPASSWORD='Prototype123!' psql -h 104.197.163.23 -U postgres -d postgres -c "
SELECT
  SUM(CASE WHEN name NOT LIKE 'internal_memo_%' AND status_flag = 'flagged'     THEN 1 ELSE 0 END) AS \"Correct PII detections (TP)\",
  SUM(CASE WHEN name     LIKE 'internal_memo_%' AND status_flag = 'not_flagged' THEN 1 ELSE 0 END) AS \"Correct clean files (TN)\",
  SUM(CASE WHEN name     LIKE 'internal_memo_%' AND status_flag = 'flagged'     THEN 1 ELSE 0 END) AS \"Clean files wrongly flagged (FP)\",
  SUM(CASE WHEN name NOT LIKE 'internal_memo_%' AND status_flag = 'not_flagged' THEN 1 ELSE 0 END) AS \"PII files missed (FN)\",
  ROUND(100.0 * SUM(CASE WHEN name NOT LIKE 'internal_memo_%' AND status_flag = 'flagged'     THEN 1 ELSE 0 END)
    / NULLIF(SUM(CASE WHEN status_flag = 'flagged' THEN 1 ELSE 0 END), 0), 1)   AS \"Precision %\",
  ROUND(100.0 * SUM(CASE WHEN name NOT LIKE 'internal_memo_%' AND status_flag = 'flagged'     THEN 1 ELSE 0 END)
    / NULLIF(SUM(CASE WHEN name NOT LIKE 'internal_memo_%' THEN 1 ELSE 0 END), 0), 1) AS \"Recall %\",
  COUNT(*) FILTER (WHERE status_flag IN ('flagged','not_flagged')) AS \"Total scanned\",
  COUNT(*) FILTER (WHERE status_flag = 'not_checked')             AS \"Still pending\"
FROM drive_files;
"
```

### Detection stage breakdown (run after all rows are scanned)

Shows how many files were caught by each detector stage.

```bash
PGPASSWORD='Prototype123!' psql -h 104.197.163.23 -U postgres -d postgres -c "
SELECT
  detection_stage                                           AS \"Detected by\",
  COUNT(*)                                                  AS \"Files\",
  SUM(CASE WHEN status_flag = 'flagged'     THEN 1 ELSE 0 END) AS \"Flagged as PII\",
  SUM(CASE WHEN status_flag = 'not_flagged' THEN 1 ELSE 0 END) AS \"Flagged as clean\"
FROM drive_files
WHERE detection_stage IS NOT NULL
GROUP BY detection_stage
ORDER BY \"Files\" DESC;
"
```
