"""Cron job entry point for the GDPR document scanner.

Intended to run on a schedule (e.g. Cloud Scheduler → Cloud Run Jobs).
Each invocation scans a batch of documents, detects PII via regex, and
dispatches findings downstream.  When no PII is found, the no-match path
is invoked (stub — wire in your own logic).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.file_reader import extract_text
from detectors.regex import RegexDetectorConfig, detect_pii

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    file_path: str
    findings: list[dict]

    @property
    def has_pii(self) -> bool:
        return len(self.findings) > 0


# ── use-case ──────────────────────────────────────────────────────────────────

def scan_document(file_path: str | Path, config: RegexDetectorConfig | None = None) -> ScanResult:
    """Extract text from *file_path* and run the regex PII detector over it."""
    text = extract_text(file_path)
    findings = detect_pii(text, config)
    return ScanResult(file_path=str(file_path), findings=findings)


# ── downstream handlers ───────────────────────────────────────────────────────

def handle_pii_found(result: ScanResult) -> None:
    """Called when *result* contains one or more PII findings."""
    logger.info(
        "PII detected",
        extra={"file": result.file_path, "finding_count": len(result.findings)},
    )
    # TODO: persist findings, notify data owner, flag file for review, etc.


def handle_no_pii(result: ScanResult) -> None:
    """Called when *result* contains no PII findings (boilerplate — wire up as needed)."""
    logger.info("No PII found", extra={"file": result.file_path})
    # TODO: mark file as clean, update audit log, etc.


# ── orchestration ─────────────────────────────────────────────────────────────

def process_file(file_path: str | Path, config: RegexDetectorConfig | None = None) -> ScanResult:
    """Scan a single file and route to the appropriate handler."""
    result = scan_document(file_path, config)

    if result.has_pii:
        handle_pii_found(result)
    else:
        handle_no_pii(result)

    return result


def run(file_paths: list[str | Path], config: RegexDetectorConfig | None = None) -> list[ScanResult]:
    """Cron job entry point — iterate over *file_paths* and process each one."""
    results: list[ScanResult] = []

    for path in file_paths:
        try:
            results.append(process_file(path, config))
        except Exception:
            logger.exception("Failed to process file", extra={"file": str(path)})

    logger.info(
        "Scan complete",
        extra={
            "total": len(file_paths),
            "with_pii": sum(1 for r in results if r.has_pii),
            "clean": sum(1 for r in results if not r.has_pii),
        },
    )
    return results
