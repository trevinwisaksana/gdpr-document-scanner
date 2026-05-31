"""Full and delta scan orchestration.

Walks SCAN_TARGET_DIR, extracts text (reusing core.ingestion), runs the deterministic
detectors, attributes ownership, and persists findings + a ScanRun record with timing and
volume for the admin KPIs. Delta scans skip files unchanged since their last scan.

Determinism: files are processed in sorted path order; findings get stable content-derived
ids; the optional LLM is temperature 0 and content-hash cached — so re-scanning unchanged
data yields identical findings.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

from app.file_reader import extract_text
from app.KPR_functions import record_kpi_snapshot
from scanner import detectors, escalate, ownership, store

logger = logging.getLogger(__name__)

SCAN_TARGET_DIR = os.getenv("SCAN_TARGET_DIR", "./sample-data")
RETENTION_YEARS = int(os.getenv("RETENTION_YEARS", "3"))
SCAN_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}

ProgressCb = Optional[Callable[[float, str], None]]


def target_files() -> list[Path]:
    root = Path(SCAN_TARGET_DIR)
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SCAN_EXTENSIONS)


def is_past_retention(last_modified: float, now: Optional[float] = None) -> bool:
    now = now or time.time()
    return (now - last_modified) > RETENTION_YEARS * 365.25 * 86400


def _primary_name(findings: list[dict]) -> Optional[str]:
    names = [f for f in findings if f["category"] == "name"]
    names.sort(key=lambda x: (-x["confidence"], x["start"]))
    return names[0]["snippet"] if names else None


def run_scan(scan_type: str = "full", progress_cb: ProgressCb = None) -> dict:
    """Execute a scan. Returns a summary dict; full detail is persisted in scan_runs."""
    run_id = uuid.uuid4().hex[:12]
    started = time.time()
    store.create_scan_run(run_id, scan_type, started)

    files = target_files()
    total = len(files)
    escalate_fn = escalate.get_escalator()

    scanned = flagged = skipped = bytes_scanned = 0

    for i, path in enumerate(files):
        spath = str(path)
        stat = path.stat()
        mtime = stat.st_mtime

        # delta scan: skip files unchanged since their last scan
        if scan_type == "delta":
            existing = store.get_file(store.file_id(spath))
            if existing and existing["last_scanned_at"] and mtime <= existing["last_scanned_at"]:
                skipped += 1
                _report(progress_cb, i + 1, total, f"skipped {path.name}")
                store.update_scan_run(run_id, files_skipped=skipped,
                                      progress_pct=round((i + 1) / total * 100, 1))
                continue

        doc = extract_text(path.read_bytes(), spath)
        text = doc.get("full_text", "") or ""
        findings = detectors.detect_categories(text, escalate_fn=escalate_fn)

        source_type, owner_id, master_id = ownership.resolve(spath, _primary_name(findings))
        fid = store.upsert_file(spath, source_type, stat.st_size, mtime, owner_id, master_id)
        store.replace_findings(fid, findings)
        store.mark_scanned(fid, time.time())

        scanned += 1
        bytes_scanned += stat.st_size
        if findings:
            flagged += 1

        _report(progress_cb, i + 1, total, path.name)
        store.update_scan_run(
            run_id, files_scanned=scanned, bytes_scanned=bytes_scanned,
            files_flagged=flagged, files_skipped=skipped,
            progress_pct=round((i + 1) / max(total, 1) * 100, 1),
        )

    store.update_scan_run(run_id, finished_at=time.time(), status="done", progress_pct=100.0)

    try:
        snapshot = record_kpi_snapshot(run_label=f"{scan_type}:{run_id}")
        logger.info(
            "kpi snapshot recorded snapshot_id=%s run_label=%s",
            snapshot["id"],
            snapshot["run_label"],
        )
    except Exception as exc:
        logger.warning("kpi snapshot failed run_id=%s error=%s", run_id, exc)

    return {
        "run_id": run_id, "type": scan_type, "files_scanned": scanned,
        "files_flagged": flagged, "files_skipped": skipped,
        "bytes_scanned": bytes_scanned, "duration": time.time() - started,
    }


def _report(cb: ProgressCb, done: int, total: int, label: str) -> None:
    if cb:
        cb(done / max(total, 1), label)
