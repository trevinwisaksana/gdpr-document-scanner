# GDPR Data Discovery

Built for the **TECHon hackathon — Bosch GDPR challenge**. Scans Google Drive for personally identifiable information (PII), stores results in Postgres, and surfaces findings through a web dashboard.

---

## Live demo

**[https://gdpr-document-scanner-gamma.vercel.app/](https://gdpr-document-scanner-gamma.vercel.app/)**

Sign in with:

| Username | Password | View |
|----------|----------|------|
| `admin` | `admin` | Admin (Data Protection Officer) — full dashboard, KPIs, scan controls |
| `user` | `user` | Employee — file review UI |

> The frontend ships with a bundled demo dataset so every screen is interactive without a backend. When `NEXT_PUBLIC_API_BASE_URL` is set, admin KPIs and owner data switch to live Postgres data automatically.

---

## Architecture

```
Lister cronjob → Postgres → Extractor consumer → Pub/Sub → Scanner consumer → Postgres
                                                                                    ↓
                                                                        FastAPI backend (GCP Cloud Run)
                                                                                    ↓
                                                                        Next.js frontend (Vercel)
```

1. **Lister** (`jobs/listing.py`) — Cloud Run Job on a schedule. Lists all files in Google Drive and upserts metadata into the `drive_files` Postgres table.
2. **Extractor consumer** (`services/extraction_consumer.py`) — Pulls file metadata from Pub/Sub, downloads and extracts text, publishes to the scanner topic.
3. **Scanner consumer** (`services/scanner_consumer.py`) — Pulls extracted text, runs the detection pipeline, writes `status_flag`, `pii_category`, and `detection_stage` back to Postgres.
4. **FastAPI backend** (`app/main.py`) — Cloud Run service. Reads from Postgres and exposes KPI, file, and scan endpoints.
5. **Next.js frontend** (`frontend/`) — Vercel deployment. Admin dashboard + employee file review UI.

---

## Detection pipeline

Three-tier cascade in `app/process.py → scan_text()`, stops at first hit:

1. **Regex** (`detectors/regex.py`) — fast, deterministic. Emails, phones, IP addresses, credit cards, IBANs, SSNs, dates of birth, usernames, signatures, ID documents.
2. **Azure NER** (`app/NER.py`) — if regex finds nothing. Calls Azure Language Service. High-confidence findings (≥ 0.85) kept directly; low-confidence ones passed to LLM verify.
3. **LLM verify / detect** (`app/llm_fallback.py`) — confirms low-confidence NER hits, or runs a full PII scan if both regex and NER find nothing. Uses OpenRouter / Qwen.

---

## Frontend pages

### Admin view

| Page | What it shows | Data source |
|------|--------------|-------------|
| **Dashboard** | KPI cards (files registered, processed, flagged, not flagged, flag rate), file outcome donut chart, flagged files per Drive owner | Live from Postgres |
| **Scan** | Live text scanner — paste any text, run the full detection pipeline, see PII highlighted inline with category toggles | Live (calls `POST /scan/text`) |
| **History** | Trend chart of files flagged / findings / scanned per scan run | Demo data |
| **Users** | Flagged file count per Drive owner, sorted by exposure | Live from Postgres |
| **Settings** | Connector toggles (Google Drive, OneDrive, SharePoint, file share), retention period, delta scan frequency | Local (localStorage) |

### Employee view

| Page | What it shows | Data source |
|------|--------------|-------------|
| **Files** | Flagged files assigned to you, sorted by risk. Bulk actions: mark for deletion, cancel (false positive), extend retention. Search and filter. | Demo data |
| **File viewer** | Document preview with PII highlighted inline, prev/next navigation through flagged files, per-finding cards (category, confidence, GDPR articles, snippet), AI summary via local Ollama | Demo data |
| **Stats** | Files assigned / deleted / pending / cancelled / extended, category breakdown donut, review progress | Demo data |
| **Settings** | Hide low-risk files, sort order, compact view, Ollama model selection, notification preferences | Local (localStorage) |

---

## Backend API endpoints

Base URL: `https://dashboard-http-95861934207.us-central1.run.app`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/scan/text` | Scan raw text through the full detection pipeline (regex → NER → LLM) |
| `GET` | `/kpis/total-files-registered` | Total files in Drive |
| `GET` | `/kpis/total-files-flagged` | Files with PII found |
| `GET` | `/kpis/total-files-processed` | Files scanned |
| `GET` | `/kpis/percentage-files-flagged` | Flag rate |
| `GET` | `/kpis/owners` | All Drive file owners |
| `GET` | `/kpis/flagged-files-per-owner` | Flagged file count per owner |
| `GET` | `/users/{user_id}/files` | Flagged files for a user |
| `PATCH` | `/findings/{finding_id}/status` | Update finding decision (`keep` / `delete` / `false_positive`) |
| `POST` | `/workflows/drive/scan` | Trigger a Google Drive scan |

---

## Run the frontend locally

```bash
cd frontend
npm install
cp .env.example .env.local   # optional — runs on demo data without it
npm run dev
# open http://localhost:3000
```

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | _(empty)_ | GCP Cloud Run base URL. Leave blank for full demo mode. |
| `NEXT_PUBLIC_DEMO_MODE` | `false` | Force demo mode even if API URL is set. |
| `NEXT_PUBLIC_OLLAMA_URL` | `http://localhost:11434` | Local Ollama for AI file summaries (called from the browser). |
| `NEXT_PUBLIC_OLLAMA_MODEL` | `llama3.2` | Ollama model to use. |

For the Ollama summary to work: `OLLAMA_ORIGINS=* ollama serve`

---

## Run the backend locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Postgres connection string (reads `drive_files` + `kpi_snapshots`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON (`credentials.json`) |
| `SOURCE_FOLDER_ID` | Google Drive folder to scan (`root` for all) |
| `PUBSUB_SUBSCRIPTION` | Pub/Sub subscription for each consumer |
| `SCANNER_PUBSUB_TOPIC` | Pub/Sub topic the extractor publishes to |
| `NER_SUBSCRIPTION_KEY` | Azure Language service key |
| `OPENROUTER_API_KEY` | OpenRouter API key (LLM fallback) |
| `OPENROUTER_MODEL` | Model to use (default: `qwen/qwen3-8b`) |

---

## Deployment

### Frontend → Vercel
1. In Vercel → New Project → import this repo
2. Set **Root Directory** to `frontend/`
3. Add environment variables (optional)
4. Deploy

### Backend → Google Cloud Run
Cloud Build (`cloudbuild.yaml`) builds and deploys the scanner consumer automatically on push.

Manual deploy:
```bash
gcloud builds submit --config cloudbuild.yaml
```

| Dockerfile | Service |
|------------|---------|
| `Dockerfile` | Dashboard HTTP (FastAPI backend) |
| `Dockerfile.job` | Lister cronjob |
| `Dockerfile.consumer` | Extractor consumer |
| `Dockerfile.scanner` | Scanner consumer |

---

## Supported file types

`PDF`, `DOCX`, `PPTX`, `XLSX`, `XLS`, `CSV`, `TXT`, `HTML`, `RTF`

---

## Tests

```bash
pytest
```
