#!/usr/bin/env bash
# One-command launch. Creates venv + installs deps on first run, then starts the app.
set -euo pipefail
cd "$(dirname "$0")"

PY=python3.10
command -v "$PY" >/dev/null 2>&1 || PY=python3

if [ ! -d venv ]; then
  echo "Creating venv…"
  "$PY" -m venv venv
  ./venv/bin/pip install --quiet --upgrade pip
  ./venv/bin/pip install --quiet -r requirements.txt
  ./venv/bin/python -m spacy download en_core_web_lg
fi

# Sample data is committed; clone only if a clean checkout is missing it.
if [ ! -d sample-data ] || [ -z "$(ls -A sample-data 2>/dev/null)" ]; then
  echo "Fetching sample data…"
  git clone --depth 1 https://github.com/a-klumpp/GDPR-data-samples sample-data
fi

[ -f .env ] || cp .env.example .env

exec ./venv/bin/streamlit run app.py
