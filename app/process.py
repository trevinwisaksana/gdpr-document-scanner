"""Cron job entry point for the GDPR document scanner.

Intended to run on a schedule (e.g. Cloud Scheduler → Cloud Run Jobs).
Each invocation scans a batch of documents, detects PII via regex, and
dispatches findings downstream.  When no PII is found, the no-match path
is invoked (stub — wire in your own logic).
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.extraction.reader import extract_text
from app.detection.ner import ner_inference
from app.detection.llm_fallback import llm_detect_pii, llm_verify_findings
from detectors.regex import (
    RegexDetectorConfig, detect_pii,
    NAME, EMAIL, PHONE, IP_ADDRESS,
)

logger = logging.getLogger(__name__)

# Matches lines like "Owner: Team Lead" or "Date: 05 May 2026".
# The label (before the colon) is never PII — strip it so NER only sees values.
_FORM_LABEL_RE = re.compile(r"^[^:\n]{1,40}:\s*", re.MULTILINE)


def _strip_form_labels(text: str) -> str:
    """Remove 'Label: ' prefixes from structured form-field lines."""
    return _FORM_LABEL_RE.sub("", text)


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
    stage: str = "regex"
    category: str | None = None

    @property
    def has_pii(self) -> bool:
        return len(self.findings) > 0


def _primary_category(findings: list[dict]) -> str | None:
    """Return the single best category for a file, preferring highest confidence."""
    if not findings:
        return None
    best = max(
        enumerate(findings),
        key=lambda item: ((item[1].get("confidence") or 0), -item[0]),
    )[1]
    return best.get("category")


# ── use-case ──────────────────────────────────────────────────────────────────

def scan_text(text: str, file_id: str, config: RegexDetectorConfig | None = None) -> ScanResult:
    """Run the PII detector on already-extracted *text*."""
    import time
    skip_llm = os.environ.get("SKIP_LLM", "").lower() in ("1", "true")
    t_total = time.perf_counter()
    timings: dict[str, float] = {}
    stage = "regex"

    t0 = time.perf_counter()
    findings = detect_pii(text, config)
    timings["regex_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    category = _primary_category(findings)

    if not findings:
        try:
            t0 = time.perf_counter()
            ner_entities = ner_inference(_strip_form_labels(text))
            ner_findings = _ner_to_findings(ner_entities)
            timings["ner_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            stage = "ner"

            if skip_llm:
                findings = ner_findings
            else:
                high_conf = [f for f in ner_findings if (f.get("confidence") or 0) >= 0.9]
                low_conf  = [f for f in ner_findings if (f.get("confidence") or 0) <  0.9]

                if low_conf:
                    t0 = time.perf_counter()
                    verified = llm_verify_findings(text, low_conf)
                    timings["llm_verify_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                    stage = "ner+llm_verify"
                else:
                    verified = []

                findings = high_conf + verified

            category = _primary_category(findings)
        except Exception:
            logger.warning("NER fallback failed", extra={"file": file_id})

    if not findings and not skip_llm:
        t0 = time.perf_counter()
        findings = llm_detect_pii(text)
        timings["llm_detect_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        stage = "llm_detect"
        category = _primary_category(findings)

    timings["total_ms"] = round((time.perf_counter() - t_total) * 1000, 1)

    logger.info(
        "scan_metrics file_id=%s stage=%s findings=%d %s",
        file_id, stage, len(findings),
        " ".join(f"{k}={v}" for k, v in timings.items()),
    )

    return ScanResult(file_path=file_id, findings=findings, stage=stage, category=category)


def scan_document(file_path: str | Path, config: RegexDetectorConfig | None = None) -> ScanResult:
    """Extract text from *file_path* then scan it."""
    text = extract_text(file_path)
    return scan_text(text, str(file_path), config)


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
