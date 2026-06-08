"""Document-type classifier for targeted PII detection.

Uses weighted keyword scoring over the first 2000 chars of text plus the
filename stem. Returns a ClassificationResult with doc_type and confidence.

If confidence < CONFIDENCE_THRESHOLD the caller should fall back to running
all detectors (the `generic` profile) — false negatives are worse than
false positives for GDPR compliance.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

CONFIDENCE_THRESHOLD: Final[float] = 0.5
_TEXT_WINDOW: Final[int] = 2000

# ── keyword tables ─────────────────────────────────────────────────────────────
# Each entry is (keyword_lowercase, weight). Keywords are matched as plain
# substrings against a lowercased text window — fast and dependency-free.
#
# Saturation cap: the total text score contribution is clamped to 0.4 so that
# a very keyword-dense document doesn't overwhelm a filename signal.
# Effective score = filename_prior (0–0.6) + min(sum_of_hits, saturation_cap)

_SATURATION_CAP: Final[float] = 0.4

_TEXT_KEYWORDS: dict[str, list[tuple[str, float]]] = {
    "hr_form": [
        ("employee id", 0.15), ("national insurance", 0.15), ("payroll", 0.12),
        ("onboarding", 0.12), ("employment contract", 0.14), ("annual leave", 0.10),
        ("salary band", 0.12), ("personnel number", 0.13), ("probationary", 0.11),
        ("performance review", 0.10), ("employee", 0.06), ("department", 0.05),
        ("job title", 0.07), ("hire date", 0.08), ("human resources", 0.09),
        ("date of birth", 0.10), ("social security", 0.12), ("next of kin", 0.13),
        ("emergency contact", 0.11), ("notice period", 0.08),
    ],
    "invoice": [
        ("invoice number", 0.20), ("invoice no", 0.18), ("bill to", 0.18),
        ("payment due", 0.16), ("vat number", 0.16), ("subtotal", 0.14),
        ("amount due", 0.16), ("bank account", 0.14), ("purchase order", 0.13),
        ("po number", 0.13), ("remittance", 0.12), ("invoice", 0.07),
        ("quantity", 0.05), ("unit price", 0.07), ("tax", 0.04),
        ("due date", 0.07), ("net 30", 0.10), ("net 60", 0.10),
        ("vat", 0.06), ("total", 0.04),
    ],
    "contract": [
        ("whereas", 0.18), ("hereinafter", 0.20), ("governing law", 0.18),
        ("indemnification", 0.18), ("force majeure", 0.18), ("confidentiality clause", 0.18),
        ("termination notice", 0.16), ("liability", 0.10), ("breach", 0.10),
        ("terms and conditions", 0.14), ("agreement", 0.06), ("parties", 0.06),
        ("clause", 0.07), ("obligations", 0.08), ("effective date", 0.08),
        ("jurisdiction", 0.12), ("warranty", 0.08), ("indemnify", 0.14),
        ("binding arbitration", 0.16), ("executed by", 0.12),
    ],
    "id_document": [
        ("passport number", 0.25), ("date of expiry", 0.22), ("place of birth", 0.22),
        ("nationality", 0.15), ("issuing authority", 0.22), ("document number", 0.20),
        ("personal number", 0.18), ("reisepass", 0.25), ("personalausweis", 0.25),
        ("identity card", 0.20), ("mrz", 0.20), ("surname", 0.08),
        ("given names", 0.10), ("driving licence", 0.18), ("driving license", 0.18),
        ("expiry date", 0.14), ("date of issue", 0.14), ("holder", 0.06),
        ("sex", 0.04), ("height", 0.06),
    ],
    "medical": [
        ("diagnosis", 0.20), ("prescription", 0.20), ("medical history", 0.20),
        ("icd", 0.18), ("clinical", 0.14), ("treatment", 0.12),
        ("medication", 0.16), ("health record", 0.20), ("physician", 0.16),
        ("blood type", 0.18), ("allergy", 0.14), ("patient", 0.10),
        ("referral", 0.12), ("discharge", 0.14), ("dosage", 0.16),
        ("gp", 0.08), ("next of kin", 0.10), ("nhs", 0.14),
        ("symptoms", 0.10), ("consultant", 0.08),
    ],
    "correspondence": [
        ("dear ", 0.18), ("yours sincerely", 0.20), ("yours faithfully", 0.20),
        ("kind regards", 0.16), ("to whom it may concern", 0.22),
        ("please find attached", 0.18), ("i am writing", 0.16),
        ("follow up", 0.12), ("re:", 0.10), ("subject:", 0.08),
        ("regards", 0.07), ("sincerely", 0.08), ("cc:", 0.08),
        ("bcc:", 0.09), ("forwarded", 0.08), ("reply", 0.05),
        ("attachment", 0.07), ("enclosed", 0.09), ("as discussed", 0.10),
        ("further to", 0.12),
    ],
    "financial": [
        ("balance sheet", 0.20), ("profit and loss", 0.20), ("income statement", 0.20),
        ("cash flow", 0.18), ("fiscal year", 0.16), ("quarterly report", 0.16),
        ("dividend", 0.16), ("shareholder", 0.14), ("bank statement", 0.18),
        ("account number", 0.16), ("sort code", 0.18), ("audit", 0.12),
        ("revenue", 0.08), ("assets", 0.08), ("liabilities", 0.10),
        ("equity", 0.08), ("debit", 0.07), ("credit", 0.06),
        ("transaction", 0.07), ("interest rate", 0.12),
    ],
}

_FILENAME_KEYWORDS: dict[str, list[str]] = {
    "hr_form":        ["employee", "hr", "onboarding", "personnel", "payroll",
                       "staff", "application_form", "application form", "recruitment"],
    "invoice":        ["invoice", "rechnung", "bill", "factura", "receipt"],
    "contract":       ["contract", "agreement", "nda", "msa", "sla", "terms", "vertrag"],
    "id_document":    ["passport", "identity", "ausweis", "reisepass",
                       "drivers_license", "driving_license", "id_card"],
    "medical":        ["medical", "health", "patient", "prescription",
                       "clinical", "discharge", "referral"],
    "correspondence": ["letter", "email", "correspondence", "memo", "notice"],
    "financial":      ["financial", "statement", "report", "audit",
                       "accounts", "budget", "expense", "bank"],
}


# ── classifier ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ClassificationResult:
    doc_type: str
    confidence: float


def classify_document(text: str, file_name: str = "") -> ClassificationResult:
    """Classify document type using first 2000 chars of text + filename stem.

    Always returns a valid ClassificationResult. Falls back to
    ClassificationResult("generic", 0.0) on any error or low confidence.
    """
    try:
        return _classify(text, file_name)
    except Exception:
        return ClassificationResult("generic", 0.0)


def _classify(text: str, file_name: str) -> ClassificationResult:
    scores: dict[str, float] = {dt: 0.0 for dt in _TEXT_KEYWORDS}

    # ── filename prior ─────────────────────────────────────────────────────────
    if file_name:
        stem = Path(file_name).stem.lower().replace("_", " ").replace("-", " ")
        for doc_type, triggers in _FILENAME_KEYWORDS.items():
            for trigger in triggers:
                if trigger in stem:
                    scores[doc_type] += 0.6
                    break  # one filename hit per doc type is enough

    # ── text scoring ───────────────────────────────────────────────────────────
    window = text[:_TEXT_WINDOW].lower() if text else ""
    if window:
        for doc_type, keywords in _TEXT_KEYWORDS.items():
            raw = sum(w for kw, w in keywords if kw in window)
            scores[doc_type] += min(raw, _SATURATION_CAP)

    best_type = max(scores, key=lambda dt: scores[dt])
    best_score = scores[best_type]

    if best_score < CONFIDENCE_THRESHOLD:
        return ClassificationResult("generic", best_score)

    return ClassificationResult(best_type, min(best_score, 1.0))
