#!/bin/sh
BASE="http://pubsub-emulator:8085/v1/projects/local-project"

curl -s -X PUT "$BASE/topics/gdpr-extraction" || true
curl -s -X PUT "$BASE/topics/gdpr-scanner" || true
curl -s -X PUT "$BASE/subscriptions/gdpr-extraction-sub" \
  -H "Content-Type: application/json" \
  -d '{"topic":"projects/local-project/topics/gdpr-extraction"}' || true
curl -s -X PUT "$BASE/subscriptions/gdpr-scanner-sub" \
  -H "Content-Type: application/json" \
  -d '{"topic":"projects/local-project/topics/gdpr-scanner"}' || true
echo "pubsub topics and subscriptions ready"
