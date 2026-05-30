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
from app.NER import ner_inference
from detectors.regex import (
    RegexDetectorConfig, detect_pii,
    NAME, EMAIL, PHONE, IP_ADDRESS,
)

logger = logging.getLogger(__name__)

# Maps Azure Language NER categories to the shared PII category schema.
# Categories absent from this map are not considered GDPR-relevant PII.
_NER_CATEGORY_MAP: dict[str, str] = {
    "Person": NAME,
    "PersonType": NAME,
    "Email": EMAIL,
    "PhoneNumber": PHONE,
    "Address": "home_address",
    "IPAddress": IP_ADDRESS,
}


def _ner_to_findings(entities: list[dict]) -> list[dict]:
    findings = []
    for ent in entities:
        category = _NER_CATEGORY_MAP.get(ent["category"])
        if category is None:
            continue
        findings.append({
            "category": category,
            "snippet": ent["text"],
            "confidence": ent.get("confidence"),
            "source": "ner",
        })
    return findings


@dataclass
class ScanResult:
    file_path: str
    findings: list[dict]

    @property
    def has_pii(self) -> bool:
        return len(self.findings) > 0


# ── use-case ──────────────────────────────────────────────────────────────────

def scan_document(file_path: str | Path, config: RegexDetectorConfig | None = None) -> ScanResult:
    """Extract text from *file_path*, run the regex PII detector, and fall back to NER if nothing is found."""
    text = extract_text(file_path)
    findings = detect_pii(text, config)

    if not findings:
        try:
            ner_entities = ner_inference(text)
            findings = _ner_to_findings(ner_entities)
        except Exception:
            logger.warning("NER fallback failed", extra={"file": str(file_path)})

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
