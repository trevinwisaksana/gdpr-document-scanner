# UI Handoff — GDPR Data Discovery

The Streamlit layer (`app.py` + `ui/`) is being fully replaced. This doc covers what to replicate, what to drop, what logic already exists to call, and what still needs to be bridged.

---

## What to replicate (the full feature list)

| Feature | Currently in | What you own |
|---------|-------------|-------------|
| Login screen + role routing | `ui/login.py`, `app.py` | Build real login. `employee` → My files only; `admin` → My files + Admin dashboard |
| Admin KPI cards | `ui/admin.py` `_kpis()` | 5 numbers: files scanned, files flagged, total findings, volume, last scan duration |
| Findings by PII type bar chart | `ui/admin.py` `_breakdowns()` | Horizontal bars, colour-coded by priority |
| By source bar chart | `ui/admin.py` `_breakdowns()` | Files + findings grouped by source type |
| Scan control buttons | `ui/admin.py` `_scan_control()` | 4 buttons: GDrive scan, full scan, delta scan, reset demo |
| Live scan progress | `ui/admin.py` `_run()` | Progress bar + current filename while scan runs |
| Employee file list | `ui/me.py` `render()` | Files owned by the user, sorted by risk priority, with retention warning |
| Finding cards | `ui/me.py` `_finding_card()` | Per-finding: PII type, icon, priority pill, confidence bar, GDPR articles, snippet, why-text |
| Review actions | `ui/me.py` buttons | Two buttons per finding: "Needed for business" / "Mark for deletion" |
| Review progress bar | `ui/me.py` | % of files fully reviewed — shown at top of employee view |

---

## What to drop

### Streamlit glue — don't port any of this

- `st.session_state` → replace with your framework's auth/session
- `st.rerun()` → Streamlit reactivity, not needed elsewhere
- `st.spinner` / `st.progress` → replace with real loading components
- `shell.inject_css()` + all `unsafe_allow_html=True` blocks → custom CSS hacked into Streamlit, rewrite properly
- `shell.esc()`, `shell.navbar()`, `shell.section_label()`, `shell.kpi_grid()` → Streamlit layout wrappers, all in `ui/shell.py`
- The entire `ui/shell.py` file

### Old scanner logic — replaced by Trevin's pipeline

**`scanner/scan.py` and `scanner/detectors.py` are NOT the real algorithm.** Regex-only, used just to power the Streamlit demo. Do not use for the new UI.

| Drop | Replace with |
|------|-------------|
| `scanner/scan.py` — walks sample files, regex only | `app/process.py:scan_text()` — real 3-tier pipeline |
| `scanner/detectors.py` — thin regex wrapper | `app/process.py` handles detection end-to-end |
| `scanner/escalate.py` — simple OpenRouter toggle | LLM fallback built into `app/process.py` already |

---

## The real detection algorithm — `app/process.py`

**This is what backs all scans in the new UI.** Three-tier cascade, stops at first hit:

1. **Regex** (`detectors/regex.py`) — fast, deterministic. Emails, phones, IBANs, SSNs, IDs, credit cards, DOBs.
2. **Azure NER** (`app/NER.py`) — if regex finds nothing, calls Azure Language Service. Catches names, addresses, etc. Needs `NER_SUBSCRIPTION_KEY` env var.
3. **LLM fallback** (`app/llm_fallback.py`) — if NER also misses. Also re-verifies low-confidence NER hits.

```python
from app.process import scan_text

result = scan_text(text: str, file_id: str)
# result.has_pii      → bool
# result.file_path    → file_id passed in
# result.findings     → list of dicts (see shape below)
```

**Finding shape out of `app/process.py`:**
```python
{
    "category":   str,    # PII category key — see 13 categories table below
    "snippet":    str,    # text excerpt containing the PII
    "confidence": float,  # 0.0–1.0
    "source":     str,    # "regex" | "ner" | "llm"
}
```

---

## The merge gap — what needs to be bridged

`app/process.py` returns raw findings. The UI needs more than that. **This bridge does not exist yet and needs to be built.**

### Problem: finding shapes don't match

What `app/process.py` returns vs what the UI needs:

| Field | `app/process.py` output | UI needs |
|-------|------------------------|---------|
| `category` | ✅ present | ✅ |
| `snippet` | ✅ present | ✅ |
| `confidence` | ✅ present | ✅ |
| `source` / `detector` | `"source"` key | UI expects `"detector"` key |
| `gdpr_articles` | ❌ missing | ✅ needed for finding card |
| `status` | ❌ missing | ✅ needed for review actions |
| `id` | ❌ missing | ✅ needed to call `set_finding_status()` |

### Solution: enrich findings before saving

After calling `scan_text()`, enrich each finding using `scanner/gdpr.py` before persisting:

```python
from app.process import scan_text
from scanner import gdpr, store, ownership
import json, time

def run_and_persist(file_path: str, text: str) -> None:
    result = scan_text(text, file_path)

    # enrich findings with GDPR metadata
    enriched = []
    for f in result.findings:
        enriched.append({
            **f,
            "detector": f["source"],                          # rename source → detector
            "gdpr_articles": json.dumps(gdpr.articles_for(f["category"])),
            "start": 0,                                       # offset not tracked by app/process.py
        })

    # persist to SQLite so review actions work
    stat = Path(file_path).stat()
    source_type, owner_id, master_id = ownership.resolve(file_path, None)
    fid = store.upsert_file(file_path, source_type, stat.st_size, stat.st_mtime, owner_id, master_id)
    store.replace_findings(fid, enriched)
    store.mark_scanned(fid, time.time())
```

This is the scan orchestration the new UI needs to implement for the Full scan and Delta scan buttons.

---

## What to keep from the original codebase

These modules are still valid and should be used as-is:

| Module | What it does | Key functions |
|--------|-------------|---------------|
| `scanner/store.py` | All SQLite reads/writes | `kpis()`, `files_for_user()`, `findings_for_file()`, `category_breakdown()`, `source_breakdown()`, `set_finding_status()`, `upsert_file()`, `replace_findings()` |
| `scanner/gdpr.py` | Category metadata — labels, icons, priorities, GDPR articles, why-text | `label()`, `icon()`, `priority()`, `articles_for()`, `WHY` dict |
| `scanner/seed.py` | Demo reset | `seed(force=True)` |
| `scanner/ownership.py` | File → user attribution | `resolve(path, primary_name)` |
| `detectors/regex.py` | Already used by `app/process.py` as step 1 — no change needed | — |

---

## Data sources

### SQLite `data/gdpr.db` — demo scan results

Backing store for everything in the demo. Path from `GDPR_DB` env var.

```python
# scanner/store.py
kpis() → {
    "files_scanned":      int,
    "files_flagged":      int,
    "total_findings":     int,
    "bytes_scanned":      int,    # format as e.g. "4.2 MB"
    "last_scan_type":     str | None,   # "full" | "delta"
    "last_scan_duration": float | None, # seconds
    "last_scan_progress": float,        # 0–100
    "last_scan_skipped":  int,
}

category_breakdown() → [{ "category": str, "n": int }, ...]   # sorted by n DESC

source_breakdown() → [{ "source_type": str, "n_files": int, "n_findings": int }, ...]
# source_type ∈ { "onedrive", "sharepoint", "fileshare" }

files_for_user(user_id) → [
    {
        "id", "path", "source_type", "size_bytes",
        "last_modified",           # unix timestamp
        "owner_user_id",
        "master_of_data_user_id",
        "last_scanned_at",
        "n_findings",              # from JOIN — only files with ≥1 finding returned
    }
]

findings_for_file(file_id) → [
    {
        "id", "file_id",
        "category",      # PII category key
        "snippet",       # text excerpt
        "confidence",    # 0.0–1.0
        "detector",      # "regex" | "ner" | "llm"
        "gdpr_articles", # JSON string e.g. '["Art. 5", "Art. 17"]'
        "status",        # "open" | "confirmed_required" | "marked_for_deletion"
        "created_at",
    }
]

set_finding_status(finding_id, status)
# status ∈ { "open", "confirmed_required", "marked_for_deletion" }
```

### Postgres `drive_files` — GDrive scan results

Written by Trevin's background pipeline. No CREATE TABLE in codebase yet — schema inferred:

```sql
CREATE TABLE drive_files (
    file_id           TEXT PRIMARY KEY,
    name              TEXT,
    owner             TEXT,       -- Google account email
    google_created_at TIMESTAMP,
    is_deleted        BOOLEAN,
    last_seen_at      TIMESTAMP,
    status_flag       TEXT        -- NULL | 'flagged' | 'not_flagged'
);
```

> ⚠️ Postgres only has `flagged`/`not_flagged` per file. **Individual finding details (snippet, category, confidence) do not exist in Postgres yet** — that's a gap Trevin needs to fill. Do not build GDrive finding cards until it's wired.

---

## Scan buttons — what each should do

| Button | Action |
|--------|--------|
| ☁️ Scan Google Drive | `POST https://gdpr-document-scanner-lotcfrcujq-uc.a.run.app/workflows/drive/scan` with body `{}` — fire and forget, returns `{"status": "triggered"}` immediately |
| ▶ Full scan | Walk `./sample-data`, call `app/process.py:scan_text()` per file, enrich + persist via `scanner/store.py` (see merge gap section) |
| ⏩ Delta scan | Same as full scan but skip files where `last_scanned_at >= last_modified` |
| ↻ Reset demo | Call `scanner/seed.seed(force=True)` — wipes DB, re-seeds users, re-runs scan |

**Live progress** — for full/delta scan, emit per-file progress:
```python
# fraction = files_done / total_files  (0.0–1.0)
# label = current filename
```

**Scan summary** to show on completion:
```python
{ "files_scanned": int, "files_flagged": int, "files_skipped": int, "duration": float }
```

---

## Employee view

### File list

- Call `store.files_for_user(user_id)` — returns only files with findings, already filtered to user's ownership
- Sort by risk priority (high → medium → low), then by number of findings descending
- **Retention warning**: show badge if `(now - last_modified) > 3 * 365.25 * 86400` seconds
- File-level priority = highest priority among its open findings (`gdpr.priority(category)`)

### Finding cards

Each card shows:
- PII type: `gdpr.label(category)` + `gdpr.icon(category)`
- Priority pill: `gdpr.priority(category)` → colour (high `#dc2626`, medium `#d97706`, low `#7e92a8`)
- Confidence bar: `confidence * 100`% — `≥80%` = likely, `50–79%` = possible, `<50%` = low
- Detector badge: `finding["detector"]` (`regex` / `ner` / `llm`)
- Snippet: `finding["snippet"]`
- GDPR articles: parse `json.loads(finding["gdpr_articles"])` → show as pills
- Why text: `gdpr.WHY[category]`
- Status badge: show if `confirmed_required` or `marked_for_deletion`

### Review actions

Two buttons per finding, call `store.set_finding_status(finding_id, status)`:

| Button | Status | Badge after |
|--------|--------|-------------|
| "Needed for business" | `confirmed_required` | ✓ Required for business |
| "Mark for deletion" | `marked_for_deletion` | 🗑 Marked for deletion |

**Review progress** at top of view:
```python
reviewed = files where ALL findings.status != "open"
pct = reviewed / total_files * 100
```

---

## The 13 PII categories (`scanner/gdpr.py`)

| key | label | icon | priority | GDPR articles |
|-----|-------|------|----------|---------------|
| `name` | Name | 👤 | low | Art. 5, 17 |
| `username` | Username / login | 🆔 | low | Art. 5, 17 |
| `email` | Email address | 📧 | medium | Art. 5, 17, 25 |
| `signature` | Signature | ✍️ | **high** | Art. 5, 17, 25, 32 |
| `photo_video` | Photo / video | 📷 | **high** | Art. 5, 17, 25, 32 |
| `phone` | Phone number | 📞 | medium | Art. 5, 17, 25 |
| `fax` | Fax number | 📠 | medium | Art. 5, 17, 25 |
| `home_address` | Home address | 🏠 | medium | Art. 5, 17, 25 |
| `billing_shipping_address` | Billing / shipping | 📦 | medium | Art. 5, 17, 25 |
| `passport` | Passport number | 🛂 | **high** | Art. 5, 17, 25, 32 |
| `id_card` | ID card number | 🪪 | **high** | Art. 5, 17, 25, 32 |
| `drivers_license` | Driver's license | 🚗 | **high** | Art. 5, 17, 25, 32 |
| `travel_history` | Travel history | ✈️ | low | Art. 5, 17 |

### GDPR articles

| Article | Meaning |
|---------|---------|
| Art. 5 | Data minimisation & storage limitation |
| Art. 17 | Right to erasure (right to be forgotten) |
| Art. 25 | Data protection by design and by default |
| Art. 32 | Security of processing |

---

## GCP pipeline (Trevin — background, UI reads results only)

```
Cloud Scheduler
  → jobs/listing.py              crawls Google Drive, upserts file metadata to Postgres
  → jobs/extraction.py           reads unprocessed files from Postgres, publishes to Pub/Sub
       → extraction_consumer.py  downloads file, extracts text, publishes to scanner topic
            → scanner_consumer.py  runs app/process.py:scan_text(), writes status_flag to Postgres
```

### What's not fully implemented yet

| Component | Status |
|-----------|--------|
| `jobs/listing.py` — Postgres upsert | ❌ stub comment only, no actual DB write |
| `jobs/extraction.py` — Postgres read | ❌ `files = []` hardcoded |
| `services/extraction_consumer.py` | ✅ works |
| `services/scanner_consumer.py` | ✅ works, writes `status_flag` |
| Individual findings in Postgres | ❌ only `status_flag` written, no snippets/categories |

---

## Demo accounts (`scanner/seed.py`)

| id | name | email | role |
|----|------|-------|------|
| `steward_comp` | Amara Okafor | amara.okafor@bosch.example | employee (has files) |
| `emp_clean` | Tom Richter | tom.richter@bosch.example | employee (empty state — intentional) |
| `admin_dpo` | Klaus Weber | klaus.weber@bosch.example | admin |

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GDPR_DB` | `data/gdpr.db` | SQLite path |
| `SCAN_TARGET_DIR` | `./sample-data` | Local files to scan |
| `RETENTION_YEARS` | `3` | Retention window for past-due badge |
| `NER_SUBSCRIPTION_KEY` | required | Azure Language Service key — NER tier won't run without it |
| `OPENROUTER_API_KEY` | optional | LLM fallback via OpenRouter |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | LLM model |
| `DATABASE_URL` | required for GDrive | Postgres connection string |
| `ALLOWED_ORIGINS` | `*` | CORS for FastAPI |

---

## FastAPI endpoints (Cloud Run)

Base URL: `https://gdpr-document-scanner-lotcfrcujq-uc.a.run.app`

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `GET` | `/health` | — | `{"status": "ok"}` |
| `POST` | `/scan/text` | `{ text, file_id?, config? }` | `{ file_path, findings[], has_pii }` |
| `POST` | `/workflows/drive/scan` | `{}` | `{"status": "triggered"}` — async, scan runs in background |

> ⚠️ `/workflows/drive/scan` currently discards results — they are not written to any DB. Do not surface GDrive scan results until Trevin wires Postgres persistence.
