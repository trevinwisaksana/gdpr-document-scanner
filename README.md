# GDPR Document Scanner

A background job that scans documents for personally identifiable information (PII) and GDPR-relevant data. Runs on a schedule via Cloud Scheduler, deployed to Cloud Run.

## Architecture

```
app/
  main.py        Entry point — structured JSON logging, lifespan hooks
  process.py     Cron job orchestration — scan files, route findings to handlers
  file_reader.py Text extraction for PDF, DOCX, PPTX, XLSX, CSV, HTML, RTF, and plain text
detectors/
  regex.py       Pure-regex PII detector — no NER or external model dependencies
tests/           pytest test suite
```

**Deployment**: Cloud Build (`cloudbuild.yaml`) builds a Docker image, pushes to Artifact Registry (`us-central1`), and deploys to Cloud Run using the commit SHA as the image tag. Cloud Scheduler triggers the job on a cron schedule.

## Detected PII categories

The regex detector covers 19 categories:

| Category | Description |
|---|---|
| `name` | Person names via label proximity |
| `username` / `user_id` | Login names, employee IDs (e.g. `E-20491`) |
| `email` | Email addresses |
| `phone` / `fax` | Phone and fax numbers (international formats) |
| `home_address` | Street addresses, German postal codes |
| `billing_shipping_address` | Billing and shipping addresses |
| `passport` | Passport numbers |
| `id_card` | National ID / tax ID / VAT ID |
| `drivers_license` | Driver's licence numbers |
| `signature` | Signature blocks |
| `photo_video` | References to photo/video files or attachments |
| `travel_history` | Itineraries, flight references, trip mentions |
| `ip_address` | IPv4 and IPv6 addresses |
| `credit_card` | Visa, MC, Amex, Discover card numbers |
| `iban` | International bank account numbers |
| `ssn` | US Social Security Numbers |
| `nhs_number` | UK NHS numbers |
| `date_of_birth` | Labelled date-of-birth fields |

## Run locally

```bash
pip install -r requirements.txt
python -m app.process
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | Port the Cloud Run job listens on |

Copy `.env.example` to `.env` to set these locally.

## Cron job / batch processing

`app/process.py` is the scheduled-job entry point. Call `run(file_paths)` with a list of file paths to scan them and route findings:

```python
from app.process import run, RegexDetectorConfig

results = run(["report.pdf", "employees.csv"])
# Each result: ScanResult(file_path, findings=[{category, start, end, snippet}])
```

Disable specific detectors via `RegexDetectorConfig`:

```python
from detectors.regex import RegexDetectorConfig
config = RegexDetectorConfig(ip_addresses=False, travel=False)
results = run(file_paths, config=config)
```

## Supported file types

`PDF`, `DOCX`, `PPTX`, `XLSX` / `XLS`, `CSV`, `HTML`, `RTF`, `TXT`, `MD`, `LOG`, `JSON`, `XML`, `YAML`

## Tests

```bash
pytest
```

## Deployment

Triggered automatically by Cloud Build on push. Manual deploy:

```bash
gcloud builds submit --config cloudbuild.yaml
```

The container runs as a non-root `appuser` (see `Dockerfile`). Logs are structured JSON, compatible with Cloud Logging.
