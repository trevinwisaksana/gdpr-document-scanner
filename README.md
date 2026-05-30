# GDPR Data Discovery

Scan a folder of unstructured documents, detect the 13 categories of personal data, attribute
each finding to a responsible person, flag files past the 3-year retention window, and let a
human make the final delete decision. Built for the TECHon hackathon — Bosch *Automated GDPR
Compliance* challenge.

## Run

```bash
./start.sh
```

First run creates a venv, installs deps, downloads the spaCy model, and opens the app. The
SQLite store seeds demo users and runs an initial scan automatically, so the UI is populated on
first boot. No API key required — detection is deterministic by default.

## 60-second demo script

1. **Login** — pick `Jonas Keller` (employee). You see only the files he is responsible for,
   each with a finding count and a retention badge.
2. Open a file → **GDPR finding cards**: category, snippet, confidence, the GDPR article that
   applies and why, and the responsible owner. Hit **Required for business** or **Mark for
   deletion** — nothing auto-deletes; the human has the last word.
3. Switch account → `Klaus Weber (DPO)` (admin). **Admin dashboard**: KPI cards (files scanned,
   flagged, volume, last scan duration, total findings), category and source breakdowns.
4. **Run Full Scan** — progress bar moves. **Run Delta Scan** immediately after — reports almost
   every file skipped (only changed files re-scanned). Re-run Full on unchanged data → identical
   findings (stable content-derived IDs = reproducible).
5. **Reset demo** returns to a clean, known state.

State lives in SQLite (`data/gdpr.db`), so it survives tab backgrounding.

## How detection works

Deterministic-first. Cheap, reproducible regex + label-proximity detectors run on every file;
spaCy/Presidio NER supplies names and locations. An LLM (OpenRouter) is **optional and off by
default** — it only confirms low-confidence spans, runs at temperature 0, and is content-hash
cached. The full flow works with no API key.

The 13 categories — name, username, email, signature, photo/video, phone, fax, home address,
billing/shipping address, passport no., ID-card no., driver's licence, travel history — each map
to the relevant GDPR articles (Art. 5 / 17 / 25 / 32) and a responsible person via a dual-owner
model (direct owner for personal stores, Master-of-Data steward for shared stores).

## Accuracy

Hand-labeled precision/recall over a 10-file subset of the sample data:

```bash
./venv/bin/python -m scanner.accuracy
```

Latest run: **precision 0.96, recall 1.00, F1 0.98** (22 labeled items, 1 false positive). The
numbers are produced live by the detectors — nothing is hardcoded.

## Optional LLM escalation

Copy `.env.example` to `.env` and set `OPENROUTER_API_KEY` to enable. Leave it blank for
deterministic-only. The key is never committed.

## Layout

```
scanner/   detectors, gdpr mapping, ownership, scan orchestration, SQLite store, seed, escalate, accuracy
ui/        shared CSS shell + login / my-files / admin views
core/      reused PII engine (Presidio + spaCy), ingestion, validator, ollama fallback
app.py     Streamlit entrypoint — session-state router over the three views
sample-data/  demo documents (default scan target)
```
# gdpr-document-scanner
# gdpr-document-scanner
