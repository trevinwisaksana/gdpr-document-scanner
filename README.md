# GDPR Data Discovery

Built for the **TECHon hackathon — Bosch GDPR challenge**. A FastAPI service that scans documents for personally identifiable information (PII) and GDPR-relevant data, containerized for Cloud Run.

---

## 🔗 Live demo

> **TODO: paste your Streamlit Cloud URL here once deployed**
> e.g. `https://yourname-gdpr-xxxx.streamlit.app`

Once that link is up, teammates just open it in a browser — no setup needed.

---

## Run locally (for development)

Only needed if you want to work on the code. Teammates who just want to see the demo should use the link above.

**You need:** Python 3.10+, Git

```bash
git pull
./start.sh
```

First run takes ~3 minutes (downloads the spaCy NLP model ~750 MB and seeds the database). After that, starts in seconds.

If port is in use: `lsof -ti:8501 | xargs kill` then re-run.

### Demo accounts

Sign in as any of these to explore different views:

| Account | Role | What you see |
|---|---|---|
| **Amara Okafor** | Employee | Her flagged files with PII findings, sorted by risk |
| **Tom Richter** | Employee | No flagged files (shows the empty state) |
| **Klaus Weber** | Admin (DPO) | Full dashboard — KPIs, scan controls, all findings |

### What the scan actually does

When the app boots (or you press **Run Full Scan** as admin), it reads the real PDF/DOCX files in `sample-data/` and runs three layers of detection:

1. **Text extraction** (`core/ingestion.py`) — `pdfplumber` / `python-docx`
2. **Regex detectors** (`scanner/detectors.py`) — label-proximity patterns for emails, phones, addresses, passport/ID numbers, names, signatures
3. **NER via spaCy + Presidio** (`core/pii_detector.py`) — catches person names the regex labels miss
4. **LLM verification** (`core/llm_fallback.py`) — optional, off by default; set `OPENROUTER_API_KEY` in `.env` to enable

Results are saved to `data/gdpr.db` (SQLite). Delta scans skip unchanged files.

### What's real vs demo data

| Thing | Real or fake? |
|---|---|
| PDF/DOCX files scanned | Real files in `sample-data/` |
| PII findings and snippets shown | Real — extracted from actual file content |
| 3-year retention flag | Real — compares actual file modification timestamps |
| NER name detection | Real — spaCy `en_core_web_lg` model |
| Demo users (Amara, Tom, Klaus) | Fake — seeded for demo purposes |
| File ownership attribution | Fake — inferred from filename keywords, not real metadata |

### Priority levels

Files and findings are sorted and coloured by risk:

| Priority | PII categories |
|---|---|
| 🔴 High | Passport, ID card, Driver's licence, Signature, Photo/video |
| 🟡 Medium | Home address, Billing/shipping address, Email, Phone, Fax |
| ⚪ Low | Name, Username/login, Travel history |

### Troubleshooting

| Problem | Fix |
|---|---|
| `./start.sh` permission denied | Run `chmod +x start.sh` first |
| Port 8501 already in use | Kill the existing process: `lsof -ti:8501 \| xargs kill` |
| Blank screen / no demo data | Delete `data/gdpr.db` and restart — forces re-seed |
| spaCy model missing | Run `venv/bin/python -m spacy download en_core_web_lg` |

---

## Deploying the Streamlit UI

The UI currently runs locally only. To share it with others:

**Option A — Streamlit Community Cloud (easiest, free)**
1. Push the repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → deploy → point at `app.py`
3. Everyone gets a public URL, no server needed

**Option B — Cloud Run (same infra as the backend)**
```bash
# Build and deploy (adjust project/region as needed)
gcloud run deploy gdpr-ui \
  --source . \
  --command "streamlit,run,app.py" \
  --args "--server.port=8080,--server.headless=true" \
  --region us-central1 \
  --allow-unauthenticated
```

---

## Backend scanner / NER pipeline

```
app/
  main.py        FastAPI entry point — `/health` and `/scan/text`
  process.py     Scan orchestration — scan files, route findings to handlers
  file_reader.py Text extraction for PDF, DOCX, PPTX, XLSX, CSV, HTML, RTF, and plain text
detectors/
  regex.py       Pure-regex PII detector — no NER or external model dependencies
tests/           pytest test suite
```

**Deployment**: Cloud Build (`cloudbuild.yaml`) builds a Docker image, pushes to Artifact Registry (`us-central1`), and deploys to Cloud Run using the commit SHA as the image tag.

### Detected PII categories

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

### Run the pipeline directly

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Or via `run.py` CLI:
```bash
python run.py ./sample-data
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | Port the Cloud Run container listens on |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins for the API |

Copy `.env.example` to `.env` to set these locally.

### Workflow endpoints

The API exposes two trigger endpoints:

```bash
POST /scan/text
POST /workflows/drive/scan
```

`/scan/text` scans already-extracted text. `/workflows/drive/scan` lists Drive files and enqueues them for extraction and PII scanning via Pub/Sub.

### Batch processing API

```python
from app.process import run, RegexDetectorConfig

results = run(["report.pdf", "employees.csv"])
# Each result: ScanResult(file_path, findings=[{category, start, end, snippet}], category=...)
```

Disable specific detectors:
```python
from detectors.regex import RegexDetectorConfig
config = RegexDetectorConfig(ip_addresses=False, ssn=False)
results = run(file_paths, config=config)
```

### Supported file types

`PDF`, `DOCX`, `PPTX`, `XLSX` / `XLS`, `CSV`, `HTML`, `RTF`, `TXT`, `MD`, `LOG`, `JSON`, `XML`, `YAML`

### Tests

```bash
pytest
```

### Deploy the backend

Triggered automatically by Cloud Build on push. Manual deploy:

```bash
gcloud builds submit --config cloudbuild.yaml
```

The container runs as a non-root `appuser` (see `Dockerfile`). Logs are structured JSON, compatible with Cloud Logging. Update `cloudbuild.yaml` if you need a different service name, region, or env var set.

### Local dev environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | Cloud Run port |
| `OPENROUTER_API_KEY` | — | Enables LLM fallback for low-confidence findings |
| `SCAN_TARGET_DIR` | `./sample-data` | Directory to scan |
| `GDPR_DB` | `./data/gdpr.db` | SQLite database path |
| `RETENTION_YEARS` | `3` | Files older than this flagged as past retention |

Copy `.env.example` to `.env` to set these locally.
