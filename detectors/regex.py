"""Pure-regex PII detector — no NER or external model dependencies.

Each pattern yields findings as:
  {"category": str, "start": int, "end": int, "snippet": str}

Category keys match scanner.gdpr constants so findings can be merged with NER-based
detectors later without remapping.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

# ── category constants (mirrors scanner/gdpr.py — no cross-package import) ────
NAME = "name"
USERNAME = "username"
EMAIL = "email"
SIGNATURE = "signature"
PHONE = "phone"
FAX = "fax"
PASSPORT = "passport"
ID_CARD = "id_card"
DRIVERS_LICENSE = "drivers_license"
# Extra structured PII not in the 13-category list
IP_ADDRESS = "ip_address"
CREDIT_CARD = "credit_card"
IBAN = "iban"
SSN = "ssn"
DATE_OF_BIRTH = "date_of_birth"

# ── compiled patterns ──────────────────────────────────────────────────────────

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Broad international phone: optional country code, groupings of 2-5 digits
_PHONE = re.compile(
    r"(?<!\w)"
    r"(?:\+\d{1,3}[\s.\-/]?)?"
    r"(?:\(?\d{2,5}\)?[\s.\-/]?){2,5}"
    r"\d{2,}"
    r"(?!\w)"
)

# IPv4
_IPV4 = re.compile(
    r"(?<!\d)(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?!\d)"
)
# IPv6 (compact — matches full and compressed forms)
_IPV6 = re.compile(
    r"(?<![:\w])(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,7}:"
    r"|:(?::[0-9A-Fa-f]{1,4}){1,7}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4}"
    r"|::(?:[fF]{4}(?::0{1,4})?:)?(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)){3}"
)

# Visa / MC / Amex / Discover — 13-16 digits with optional separators
_CREDIT_CARD = re.compile(
    r"(?<!\d)"
    r"(?:4\d{3}|5[1-5]\d{2}|6011|3[47]\d{2})"
    r"[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{0,4}"
    r"(?!\d)"
)

# IBAN: up to 34 alphanum chars, country-code prefix
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b")

# US SSN: 000-00-0000 or 9 digits
_SSN = re.compile(r"(?<!\d)(?!000|666|9\d{2})\d{3}[\s\-]\d{2}[\s\-]\d{4}(?!\d)")

# Dates of birth (labelled)
_DOB_LABEL = re.compile(
    r"(?im)\b(?:dob|date\s+of\s+birth|born|geburtsdatum|birthdate)\b"
    r"[\s:.\-]*"
    r"(?P<val>\d{1,2}[\s./\-]\d{1,2}[\s./\-]\d{2,4}|\d{4}[\s./\-]\d{2}[\s./\-]\d{2})"
)

# Signature labels
_SIGNATURE_RE = re.compile(
    r"(?im)\b(?:signature|signed\s+by|unterschrift|signature\s+block)\b\s*[:\-]\s*(?P<val>.+?)\s*$"
)

# ID-document value token — alphanumeric with optional dashes/slashes
_ID_VALUE = r"(?P<val>[A-Za-z]{0,3}[\-\s]?[A-Za-z0-9][A-Za-z0-9\-/.]{2,})"

_PASSPORT_RE = re.compile(
    rf"(?im)\b(?:passport(?:\s*(?:no\.?|number))?|reisepass)\b\s*[:\-]?\s*{_ID_VALUE}", re.I
)
_DRIVERS_RE = re.compile(
    rf"(?im)\b(?:driver'?s?\s*licen[cs]e(?:\s*(?:no\.?|number))?|f[üu]hrerschein)\b\s*[:\-]?\s*{_ID_VALUE}", re.I
)
_ID_CARD_RE = re.compile(
    rf"(?im)\b(?:id\s*card(?:\s*(?:no\.?|number))?|identity\s*card|personalausweis|"
    rf"ausweis(?:nummer)?|tax\s*id|vat\s*id)\b\s*[:\-]?\s*{_ID_VALUE}", re.I
)

# Generic label:value helper
def _label_value_re(labels: str) -> re.Pattern:
    return re.compile(rf"(?im)\b(?:{labels})\b\s*[:\-]\s*(?P<val>.+?)\s*$")

_NAME_RE = _label_value_re(
    r"name|employee|participant|manager|reviewer|approver|trainer|"
    r"contact\s*person|owner|requested\s*by|prepared\s*by|applicant"
)
_USERNAME_RE = _label_value_re(r"username|user\s*name|login|user\s*id|account")
_PHONE_LABEL_RE = _label_value_re(r"phone|telephone|tel|mobile|mobil|cell|telefon")
_FAX_LABEL_RE = _label_value_re(r"fax|fax\s*number|telefax")

# Employee ID shorthand e.g. "E-20491"
_EMP_ID_RE = re.compile(r"\b[A-Z]-\d{4,6}\b")

# Stopwords that look like name values but are roles/departments
_ROLE_STOPWORDS = frozenset({
    "lead", "team", "desk", "service", "ops", "governance", "manager", "reviewer",
    "approver", "participant", "owner", "trainer", "department", "it", "hr",
    "procurement", "operations", "support", "admin", "staff", "group", "office",
    "compliance", "officer", "identity", "access", "vendor", "management",
    "facility", "coordinator", "catalog", "unit", "committee", "board",
})


# ── internal helpers ───────────────────────────────────────────────────────────

def _finding(category: str, start: int, end: int, snippet: str) -> dict | None:
    snippet = snippet.strip()
    if not snippet or len(snippet) > 200:
        return None
    if not re.search(r"[A-Za-z0-9]", snippet):
        return None
    return {
        "category": category,
        "snippet": snippet,
        "source": "regex",
    }


def _looks_like_role(value: str) -> bool:
    tokens = [t.lower().strip(".") for t in value.split()]
    return bool(tokens) and all(t in _ROLE_STOPWORDS for t in tokens)


def _dedupe(findings: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for f in findings:
        key = (f["category"], f["snippet"])
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


# ── per-category detector functions ───────────────────────────────────────────

def _detect_emails(text: str) -> list[dict]:
    out = []
    for m in _EMAIL.finditer(text):
        f = _finding(EMAIL, m.start(), m.end(), m.group())
        if f:
            out.append(f)
    return out


def _detect_phones(text: str) -> list[dict]:
    out = []
    for m in _FAX_LABEL_RE.finditer(text):
        v = m.group("val")
        if re.search(r"\d", v):
            f = _finding(FAX, m.start("val"), m.end("val"), v)
            if f:
                out.append(f)
    for m in _PHONE_LABEL_RE.finditer(text):
        v = m.group("val")
        if re.search(r"\d", v):
            f = _finding(PHONE, m.start("val"), m.end("val"), v)
            if f:
                out.append(f)
    # free-standing phone numbers
    for m in _PHONE.finditer(text):
        s = m.group().strip()
        if len(re.sub(r"\D", "", s)) >= 7:
            f = _finding(PHONE, m.start(), m.end(), s)
            if f:
                out.append(f)
    return out


def _detect_names(text: str) -> list[dict]:
    out = []
    rx = re.compile(
        r"(?im)\b(?:name|employee|participant|manager|reviewer|approver|trainer|"
        r"contact\s*person|owner|requested\s*by|prepared\s*by|applicant)\b"
        r"[ \t]*[:\-][ \t]*(?P<val>[A-Z][\w.\'-]+(?:[ \t]+[A-Z][\w.\'-]+){0,3})"
    )
    for m in rx.finditer(text):
        v = m.group("val").strip()
        if "@" in v or re.search(r"\d", v) or _looks_like_role(v):
            continue
        f = _finding(NAME, m.start("val"), m.end("val"), v)
        if f:
            out.append(f)
    return out


def _detect_usernames(text: str) -> list[dict]:
    out = []
    for m in _USERNAME_RE.finditer(text):
        f = _finding(USERNAME, m.start("val"), m.end("val"), m.group("val"))
        if f:
            out.append(f)
    for m in _EMP_ID_RE.finditer(text):
        f = _finding(USERNAME, m.start(), m.end(), m.group())
        if f:
            out.append(f)
    return out


def _detect_signatures(text: str) -> list[dict]:
    out = []
    for m in _SIGNATURE_RE.finditer(text):
        f = _finding(SIGNATURE, m.start("val"), m.end("val"), m.group("val"))
        if f:
            out.append(f)
    return out


def _detect_id_documents(text: str) -> list[dict]:
    out = []
    for pattern, category in (
        (_PASSPORT_RE, PASSPORT),
        (_DRIVERS_RE, DRIVERS_LICENSE),
        (_ID_CARD_RE, ID_CARD),
    ):
        for m in pattern.finditer(text):
            v = m.group("val")
            if re.search(r"\d", v):
                f = _finding(category, m.start("val"), m.end("val"), v)
                if f:
                    out.append(f)
    return out


def _detect_ip_addresses(text: str) -> list[dict]:
    out = []
    for m in _IPV4.finditer(text):
        f = _finding(IP_ADDRESS, m.start(), m.end(), m.group())
        if f:
            out.append(f)
    for m in _IPV6.finditer(text):
        f = _finding(IP_ADDRESS, m.start(), m.end(), m.group())
        if f:
            out.append(f)
    return out


def _detect_credit_cards(text: str) -> list[dict]:
    out = []
    for m in _CREDIT_CARD.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) in (13, 15, 16):
            f = _finding(CREDIT_CARD, m.start(), m.end(), m.group())
            if f:
                out.append(f)
    return out


def _detect_iban(text: str) -> list[dict]:
    out = []
    for m in _IBAN.finditer(text):
        v = m.group()
        # IBAN must start with a valid ISO country code (2 letters) then 2 check digits
        if re.match(r"^[A-Z]{2}\d{2}", v) and len(v) >= 15:
            f = _finding(IBAN, m.start(), m.end(), v)
            if f:
                out.append(f)
    return out


def _detect_ssn(text: str) -> list[dict]:
    out = []
    for m in _SSN.finditer(text):
        f = _finding(SSN, m.start(), m.end(), m.group())
        if f:
            out.append(f)
    return out


def _detect_dob(text: str) -> list[dict]:
    out = []
    for m in _DOB_LABEL.finditer(text):
        f = _finding(DATE_OF_BIRTH, m.start("val"), m.end("val"), m.group("val"))
        if f:
            out.append(f)
    return out


# ── public API ─────────────────────────────────────────────────────────────────

@dataclass
class RegexDetectorConfig:
    """Toggle individual detectors to trade coverage for speed."""
    names: bool = True
    emails: bool = True
    phones: bool = True
    usernames: bool = True
    signatures: bool = True
    id_documents: bool = True
    ip_addresses: bool = True
    credit_cards: bool = True
    iban: bool = True
    ssn: bool = True
    dob: bool = True


def detect_pii(text: str, config: RegexDetectorConfig | None = None) -> list[dict]:
    """Scan *text* for PII using regex patterns and return a deduplicated list of findings.

    Each finding:
        {
            "category": str,  # PII type (e.g. "email", "phone")
            "start":    int,  # start char offset in text
            "end":      int,  # end char offset in text
            "snippet":  str,  # matched text
        }
    """
    if not text or not text.strip():
        return []

    cfg = config or RegexDetectorConfig()

    runners: list[tuple[bool, Callable[[str], list[dict]]]] = [
        (cfg.names,        _detect_names),
        (cfg.emails,       _detect_emails),
        (cfg.phones,       _detect_phones),
        (cfg.usernames,    _detect_usernames),
        (cfg.signatures,   _detect_signatures),
        (cfg.id_documents, _detect_id_documents),
        (cfg.ip_addresses, _detect_ip_addresses),
        (cfg.credit_cards, _detect_credit_cards),
        (cfg.iban,         _detect_iban),
        (cfg.ssn,          _detect_ssn),
        (cfg.dob,          _detect_dob),
    ]

    findings: list[dict] = []
    for enabled, fn in runners:
        if enabled:
            findings.extend(fn(text))

    return _dedupe(findings)
