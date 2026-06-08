"""Cron job entry point for the GDPR document scanner.

Intended to run on a schedule (e.g. Cloud Scheduler → Cloud Run Jobs).
Each invocation scans a batch of documents, detects PII via regex, and
dispatches findings downstream.  When no PII is found, the no-match path
is invoked (stub — wire in your own logic).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.extraction.reader import extract_text
from app.detection.ner import ner_inference, CONFIDENCE_THRESHOLD as NER_CONFIDENCE_THRESHOLD
from app.detection.llm_fallback import llm_detect_pii, llm_verify_findings
from app.detection.classifier import classify_document
from app.detection.profiles import profile_for
from detectors.regex import (
    RegexDetectorConfig, detect_pii,
    NAME, EMAIL, PHONE, IP_ADDRESS,
)

logger = logging.getLogger(__name__)

# Matches lines like "Owner: Team Lead" or "Date: 05 May 2026".
# The label (before the colon) is never PII — strip it so NER only sees values.
_FORM_LABEL_RE = re.compile(r"^[^:\n]{1,40}:\s*", re.MULTILINE)

# Maps PII category strings back to RegexDetectorConfig field names.
# Used by the miss-logging hook to check whether a detector was disabled.
_CATEGORY_TO_FLAG: dict[str, str] = {
    EMAIL:              "emails",
    PHONE:              "phones",
    "fax":              "phones",
    "username":         "usernames",
    "signature":        "signatures",
    "passport":         "id_documents",
    "id_card":          "id_documents",
    "drivers_license":  "id_documents",
    IP_ADDRESS:         "ip_addresses",
    "credit_card":      "credit_cards",
    "iban":             "iban",
    "ssn":              "ssn",
    "date_of_birth":    "dob",
    "home_address":     "emails",
}


def _strip_form_labels(text: str) -> str:
    """Remove 'Label: ' prefixes from structured form-field lines."""
    return _FORM_LABEL_RE.sub("", text)


# Maps Azure Language NER categories to the shared PII category schema.
_NER_CATEGORY_MAP: dict[str, str] = {
    "Person":         NAME,
    "PersonType":     NAME,
    "Email":          EMAIL,
    "PhoneNumber":    PHONE,
    "Address":        "home_address",
    "IPAddress":      IP_ADDRESS,
    # Presidio-specific types (not returned by Azure NER)
    "SSN":            "ssn",
    "Passport":       "passport",
    "DriversLicense": "drivers_license",
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
    doc_type: str | None = None

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


def _log_profile_miss(
    doc_type: str,
    file_id: str,
    effective_config: RegexDetectorConfig,
    ner_findings: list[dict],
) -> None:
    """Log NER findings whose regex detector was disabled by the doc-type profile."""
    for finding in ner_findings:
        category = finding.get("category", "")
        flag = _CATEGORY_TO_FLAG.get(category)
        if flag is None:
            continue
        if not getattr(effective_config, flag, True):
            logger.warning(
                "profile_miss doc_type=%s missed_category=%s file_id=%s ner_confidence=%.2f",
                doc_type, category, file_id,
                finding.get("confidence") or 0.0,
            )


# ── use-case ──────────────────────────────────────────────────────────────────

def scan_text(
    text: str,
    file_id: str,
    config: RegexDetectorConfig | None = None,
    file_name: str = "",
) -> ScanResult:
    """Run the full PII detection pipeline on already-extracted *text*.

    Stages (each is a fallback for the previous):
      1. Regex       — fast, deterministic, document-type targeted
      2. Azure NER   — high-confidence (≥0.85) kept; low-confidence → LLM verify
      3. LLM verify  — confirms low-confidence NER candidates via OpenRouter
      4. LLM detect  — full scan when regex + NER both find nothing

    Args:
        text:      Extracted plain text to scan.
        file_id:   File identifier used for logging and the returned ScanResult.
        config:    Explicit RegexDetectorConfig; overrides document-type routing.
        file_name: Original filename used by the document classifier.
    """
    import time
    t_total = time.perf_counter()
    timings: dict[str, float] = {}
    stage = "regex"

    # ── Stage 0: document classification + profile routing ────────────────────
    t0 = time.perf_counter()
    classification = classify_document(text, file_name)
    timings["classify_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    effective_config = config
    if effective_config is None and classification.doc_type != "generic":
        effective_config = profile_for(classification.doc_type)

    logger.info(
        "doc_classify file_id=%s doc_type=%s confidence=%.2f",
        file_id, classification.doc_type, classification.confidence,
    )

    # ── Stage 1: Regex ────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    findings = detect_pii(text, effective_config)
    timings["regex_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    if findings:
        stage = "regex"
    else:
        # ── Stage 2: Azure NER ────────────────────────────────────────────────
        try:
            t0 = time.perf_counter()
            ner_entities = ner_inference(_strip_form_labels(text))
            timings["ner_ms"] = round((time.perf_counter() - t0) * 1000, 1)

            high_conf = [e for e in ner_entities if (e.get("confidence") or 0) >= NER_CONFIDENCE_THRESHOLD]
            low_conf  = [e for e in ner_entities if (e.get("confidence") or 0) <  NER_CONFIDENCE_THRESHOLD]

            ner_findings = _ner_to_findings(high_conf)

            # ── Stage 3: LLM verify (low-confidence NER candidates) ───────────
            if low_conf:
                low_conf_findings = _ner_to_findings(low_conf)
                try:
                    t0 = time.perf_counter()
                    verified = llm_verify_findings(text, low_conf_findings)
                    timings["llm_verify_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                    ner_findings.extend(verified)
                except Exception:
                    logger.warning("LLM verify failed — keeping unverified NER candidates", extra={"file": file_id})
                    ner_findings.extend(low_conf_findings)

            if ner_findings:
                stage = "ner"
                findings = ner_findings

                if effective_config is not None and classification.doc_type != "generic":
                    _log_profile_miss(classification.doc_type, file_id, effective_config, ner_findings)

        except Exception:
            logger.warning("NER fallback failed", extra={"file": file_id})

        # ── Stage 4: LLM detect (nothing found yet) ───────────────────────────
        if not findings:
            try:
                t0 = time.perf_counter()
                llm_findings = llm_detect_pii(text)
                timings["llm_detect_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                if llm_findings:
                    stage = "llm_detect"
                    findings = llm_findings
            except Exception:
                logger.warning("LLM detect failed", extra={"file": file_id})

    category = _primary_category(findings)
    timings["total_ms"] = round((time.perf_counter() - t_total) * 1000, 1)

    logger.info(
        "scan_metrics file_id=%s stage=%s findings=%d doc_type=%s %s",
        file_id, stage, len(findings), classification.doc_type,
        " ".join(f"{k}={v}" for k, v in timings.items()),
    )

    return ScanResult(
        file_path=file_id,
        findings=findings,
        stage=stage,
        category=category,
        doc_type=classification.doc_type,
    )


def scan_document(file_path: str | Path, config: RegexDetectorConfig | None = None) -> ScanResult:
    """Extract text from *file_path* then scan it."""
    text = extract_text(file_path)
    return scan_text(text, str(file_path), config, file_name=Path(file_path).name)


# ── downstream handlers ───────────────────────────────────────────────────────

def handle_pii_found(result: ScanResult) -> None:
    logger.info(
        "PII detected",
        extra={"file": result.file_path, "finding_count": len(result.findings)},
    )


def handle_no_pii(result: ScanResult) -> None:
    logger.info("No PII found", extra={"file": result.file_path})


# ── orchestration ─────────────────────────────────────────────────────────────

def process_file(file_path: str | Path, config: RegexDetectorConfig | None = None) -> ScanResult:
    result = scan_document(file_path, config)
    if result.has_pii:
        handle_pii_found(result)
    else:
        handle_no_pii(result)
    return result


def run(file_paths: list[str | Path], config: RegexDetectorConfig | None = None) -> list[ScanResult]:
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
