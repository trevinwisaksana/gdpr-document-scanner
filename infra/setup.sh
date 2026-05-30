#!/usr/bin/env bash
# One-shot setup for GCP resources required by the scalable scanner.
# Run once after deploying both Cloud Run services for the first time.
#
# Required env vars (or edit the defaults below):
#   GCP_PROJECT_ID      your GCP project
#   GCS_BUCKET_NAME     bucket containing documents to scan
#   DISPATCHER_URL      Cloud Run URL of gdpr-scanner-dispatcher
#   SCANNER_URL         Cloud Run URL of gdpr-scanner-worker
#
# Optional:
#   GCP_REGION          defaults to us-central1
#   PUBSUB_TOPIC_ID     defaults to gdpr-scan-jobs
#   CRON_SCHEDULE       cron expression, defaults to "0 2 * * *" (2am UTC daily)

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
BUCKET_NAME="${GCS_BUCKET_NAME:?Set GCS_BUCKET_NAME}"
DISPATCHER_URL="${DISPATCHER_URL:?Set DISPATCHER_URL (Cloud Run URL of dispatcher)}"
SCANNER_URL="${SCANNER_URL:?Set SCANNER_URL (Cloud Run URL of scanner worker)}"

REGION="${GCP_REGION:-us-central1}"
TOPIC_ID="${PUBSUB_TOPIC_ID:-gdpr-scan-jobs}"
SUBSCRIPTION_ID="${TOPIC_ID}-sub"
DLT_TOPIC_ID="${TOPIC_ID}-dead-letter"
CRON_SCHEDULE="${CRON_SCHEDULE:-0 2 * * *}"

echo "==> Creating Pub/Sub topic: $TOPIC_ID"
gcloud pubsub topics create "$TOPIC_ID" --project="$PROJECT_ID" 2>/dev/null || echo "    (already exists)"

echo "==> Creating dead-letter topic: $DLT_TOPIC_ID"
gcloud pubsub topics create "$DLT_TOPIC_ID" --project="$PROJECT_ID" 2>/dev/null || echo "    (already exists)"

echo "==> Creating push subscription: $SUBSCRIPTION_ID"
gcloud pubsub subscriptions create "$SUBSCRIPTION_ID" \
  --topic="$TOPIC_ID" \
  --push-endpoint="${SCANNER_URL}/scan" \
  --ack-deadline=300 \
  --min-retry-delay=10s \
  --max-retry-delay=600s \
  --dead-letter-topic="$DLT_TOPIC_ID" \
  --max-delivery-attempts=5 \
  --project="$PROJECT_ID" 2>/dev/null || echo "    (already exists)"

echo "==> Creating Cloud Scheduler job: gdpr-scan-dispatch"
gcloud scheduler jobs create http gdpr-scan-dispatch \
  --location="$REGION" \
  --schedule="$CRON_SCHEDULE" \
  --uri="${DISPATCHER_URL}/dispatch" \
  --http-method=POST \
  --project="$PROJECT_ID" 2>/dev/null || \
gcloud scheduler jobs update http gdpr-scan-dispatch \
  --location="$REGION" \
  --schedule="$CRON_SCHEDULE" \
  --uri="${DISPATCHER_URL}/dispatch" \
  --http-method=POST \
  --project="$PROJECT_ID"

echo ""
echo "Setup complete."
echo ""
echo "  Dispatcher:  ${DISPATCHER_URL}/dispatch"
echo "  Scanner:     ${SCANNER_URL}/scan"
echo "  Schedule:    $CRON_SCHEDULE (UTC)"
echo "  Dead-letter: $DLT_TOPIC_ID"
echo ""
echo "To trigger a scan immediately:"
echo "  curl -X POST ${DISPATCHER_URL}/dispatch"
