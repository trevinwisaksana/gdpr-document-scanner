# Benchmark Local

When this skill is invoked, immediately begin executing every step below in order without waiting for further instructions.

Spin up the full pipeline locally via docker-compose with 20 extraction and 20 scanner instances,
run the lister against staging Google Drive, and tail logs to observe timing and detector stage
usage in real time.

## What you'll see in the logs

| Log line | Where | What it measures |
|---|---|---|
| `extracted file_id=... extraction_ms=... chars=...` | extraction-consumer | Download + text extraction time per file |
| `scan_metrics ... stage=... regex_ms=... total_ms=...` | scanner-consumer | Per-stage scan timing per file |
| `detector_usage total=50 regex=X ner=Y llm_detect=Z` | scanner-consumer | Rolling stage usage count every 50 files |

## Steps

### 1. (Re)build images if service code has changed

```bash
cd /Users/trevinwisaksana/Engineering/GDPR/gdpr-document-scanner
docker compose build extraction-consumer scanner-consumer
```

### 2. Start infrastructure

```bash
docker compose up -d postgres pubsub-emulator pubsub-setup
docker compose wait pubsub-setup
```

### 3. Clean the database

```bash
docker compose exec postgres psql -U gdpr -d gdpr -c "TRUNCATE TABLE drive_files;"
```

### 4. Start 20 extraction and 20 scanner consumers

Forward NER and LLM keys so the full detection pipeline runs.

```bash
source .env
NER_SUBSCRIPTION_KEY="${NER_SUBSCRIPTION_KEY:-}" \
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
OPENROUTER_MODEL="${OPENROUTER_MODEL:-qwen/qwen3-8b}" \
OPENROUTER_BASE_URL="${OPENROUTER_BASE_URL:-}" \
docker compose up -d \
  --scale extraction-consumer=20 \
  --scale scanner-consumer=20 \
  extraction-consumer scanner-consumer
```

### 5. Run the lister and time it

```bash
source .env
START=$(date +%s)
docker compose run --rm listing-job
echo "Lister done in $(($(date +%s) - START))s"
```

### 6. Tail logs

```bash
docker compose logs -f extraction-consumer scanner-consumer
```

Watch for `extraction_ms` per file and `detector_usage` every 50 files. Ctrl+C when done.

### 7. Show final stage breakdown + total time

```bash
docker compose exec postgres psql -U gdpr -d gdpr -c "
SELECT
  COALESCE(detection_stage, 'pending') AS stage,
  COUNT(*)                             AS files,
  SUM(CASE WHEN status_flag = 'flagged'     THEN 1 ELSE 0 END) AS flagged,
  SUM(CASE WHEN status_flag = 'not_flagged' THEN 1 ELSE 0 END) AS clean
FROM drive_files
GROUP BY detection_stage
ORDER BY files DESC;
"
```

### 8. Tear down

```bash
docker compose down -v
```
