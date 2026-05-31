#!/bin/bash
set -e

PROJECT=summer-bond-461608-i5
REGION=us-central1
REGISTRY=us-central1-docker.pkg.dev/$PROJECT/cloud-run-source-deploy
SA=drive-tester@summer-bond-461608-i5.iam.gserviceaccount.com

DATABASE_URL="postgresql://postgres:Prototype123!\@104.197.163.23:5432/postgres"
EXTRACTION_TOPIC="projects/$PROJECT/topics/gdpr-extraction"
SCANNER_TOPIC="projects/$PROJECT/topics/gdpr-scanner"
EXTRACTION_SUB="projects/$PROJECT/subscriptions/gdpr-extraction-sub"
SCANNER_SUB="projects/$PROJECT/subscriptions/gdpr-scanner-sub"

echo "=== Authenticating ==="
gcloud config set account $SA
gcloud config set project $PROJECT
gcloud auth configure-docker $REGION-docker.pkg.dev --quiet

echo "=== Creating Artifact Registry repo ==="
gcloud artifacts repositories create cloud-run-source-deploy \
  --repository-format=docker --location=$REGION --project=$PROJECT 2>/dev/null || true

echo "=== Building and pushing images ==="
docker build -f Dockerfile.consumer -t $REGISTRY/gdpr-extraction-consumer:latest .
docker push $REGISTRY/gdpr-extraction-consumer:latest

docker build -f Dockerfile.scanner -t $REGISTRY/gdpr-scanner-consumer:latest .
docker push $REGISTRY/gdpr-scanner-consumer:latest

docker build -f Dockerfile.job -t $REGISTRY/gdpr-extraction-job:latest .
docker push $REGISTRY/gdpr-extraction-job:latest

docker build -f Dockerfile.listing -t $REGISTRY/gdpr-listing-job:latest .
docker push $REGISTRY/gdpr-listing-job:latest

echo "=== Creating Pub/Sub topics and subscriptions ==="
gcloud pubsub topics create gdpr-extraction --project=$PROJECT 2>/dev/null || true
gcloud pubsub topics create gdpr-scanner --project=$PROJECT 2>/dev/null || true
gcloud pubsub subscriptions create gdpr-extraction-sub \
  --topic=gdpr-extraction --project=$PROJECT 2>/dev/null || true
gcloud pubsub subscriptions create gdpr-scanner-sub \
  --topic=gdpr-scanner --project=$PROJECT 2>/dev/null || true

echo "=== Deploying Cloud Run services ==="
gcloud run deploy gdpr-extraction-consumer \
  --image=$REGISTRY/gdpr-extraction-consumer:latest \
  --region=$REGION --project=$PROJECT \
  --no-allow-unauthenticated \
  --set-env-vars="PUBSUB_SUBSCRIPTION=$EXTRACTION_SUB,SCANNER_PUBSUB_TOPIC=$SCANNER_TOPIC"

gcloud run deploy gdpr-scanner-consumer \
  --image=$REGISTRY/gdpr-scanner-consumer:latest \
  --region=$REGION --project=$PROJECT \
  --no-allow-unauthenticated \
  --set-env-vars="PUBSUB_SUBSCRIPTION=$SCANNER_SUB,DATABASE_URL=$DATABASE_URL"

echo "=== Deploying Cloud Run jobs ==="
gcloud run jobs create gdpr-listing-job \
  --image=$REGISTRY/gdpr-listing-job:latest \
  --region=$REGION --project=$PROJECT \
  --service-account=$SA 2>/dev/null || \
gcloud run jobs update gdpr-listing-job \
  --image=$REGISTRY/gdpr-listing-job:latest \
  --region=$REGION --project=$PROJECT \
  --service-account=$SA

gcloud run jobs create gdpr-extraction-job \
  --image=$REGISTRY/gdpr-extraction-job:latest \
  --region=$REGION --project=$PROJECT \
  --service-account=$SA \
  --set-env-vars="PUBSUB_TOPIC=$EXTRACTION_TOPIC" 2>/dev/null || \
gcloud run jobs update gdpr-extraction-job \
  --image=$REGISTRY/gdpr-extraction-job:latest \
  --region=$REGION --project=$PROJECT \
  --service-account=$SA \
  --set-env-vars="PUBSUB_TOPIC=$EXTRACTION_TOPIC"

echo "=== Done ==="
echo "Services:"
gcloud run services list --project=$PROJECT --region=$REGION --format="table(SERVICE,URL)"
echo "Jobs:"
gcloud run jobs list --project=$PROJECT --region=$REGION --format="table(JOB)"
