"""Local PII detection via Microsoft Presidio + spaCy.

Replaces the Azure Language Service NER call with an on-device Presidio
AnalyzerEngine — no network round-trips, ~50–200 ms per document vs 1–3 s
for the Azure API.

The AnalyzerEngine is initialised once (singleton) and reused across calls.
"""
from __future__ import annotations

import logging

from presidio_analyzer import AnalyzerEngine

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.85

# Presidio entity types we care about → intermediary category names that
# process.py's _NER_CATEGORY_MAP already knows how to handle.
_PRESIDIO_TO_CATEGORY: dict[str, str] = {
    "PERSON":            "Person",
    "EMAIL_ADDRESS":     "Email",
    "PHONE_NUMBER":      "PhoneNumber",
    "LOCATION":          "Address",
    "IP_ADDRESS":        "IPAddress",
    "US_SSN":            "SSN",
    "US_PASSPORT":       "Passport",
    "US_DRIVER_LICENSE": "DriversLicense",
}

_ENTITIES = list(_PRESIDIO_TO_CATEGORY.keys())

_analyzer: AnalyzerEngine | None = None
_analyzer_lock = __import__("threading").Lock()


def _get_analyzer() -> AnalyzerEngine:
    global _analyzer
    if _analyzer is None:
        with _analyzer_lock:
            if _analyzer is None:
                logger.info("Initialising Presidio AnalyzerEngine (one-time startup cost)")
                _analyzer = AnalyzerEngine()
    return _analyzer


def ner_inference(
    text: str,
    mode=None,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> list[dict]:
    """Run Presidio PII analysis on *text*.

    Returns a list of {"text": str, "category": str, "confidence": float}.
    Same interface as the previous Azure implementation so process.py
    requires no structural changes.
    """
    if not text or not text.strip():
        return []

    try:
        analyzer = _get_analyzer()
        results = analyzer.analyze(
            text=text,
            entities=_ENTITIES,
            language="en",
            score_threshold=confidence_threshold,
        )
    except Exception as exc:
        logger.error("Presidio AnalyzerEngine error: %s", exc)
        return []

    findings: list[dict] = []
    for result in results:
        category = _PRESIDIO_TO_CATEGORY.get(result.entity_type)
        if category is None:
            continue
        findings.append({
            "text": text[result.start:result.end],
            "category": category,
            "confidence": result.score,
        })

    return findings


def ner_inference_batch(
    texts: list[str],
    mode=None,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> list[list[dict]]:
    """Run ner_inference over a list of texts, returning results in input order."""
    return [
        ner_inference(t, mode=mode, confidence_threshold=confidence_threshold)
        for t in texts
    ]
