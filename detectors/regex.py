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
PHOTO_VIDEO = "photo_video"
PHONE = "phone"
FAX = "fax"
HOME_ADDRESS = "home_address"
BILLING_SHIPPING = "billing_shipping_address"
PASSPORT = "passport"
ID_CARD = "id_card"
DRIVERS_LICENSE = "drivers_license"
TRAVEL_HISTORY = "travel_history"
# Extra structured PII not in the 13-category list
IP_ADDRESS = "ip_address"
CREDIT_CARD = "credit_card"
IBAN = "iban"
SSN = "ssn"
DATE_OF_BIRTH = "date_of_birth"
NHS_NUMBER = "nhs_number"

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

# German postal + city
_POSTAL_DE = re.compile(r"\b\d{5}[ \t]+[A-ZÄÖÜ][a-zäöüß]+")
# Street names (German & generic)
_STREET = re.compile(
    r"\b[A-ZÄÖÜ][a-zäöüß.]+(?:str\.?|straße|gasse|weg|allee|platz|road|rd\.?|"
    r"street|st\.?|avenue|ave\.?|lane|ln\.?|drive|dr\.?|boulevard|blvd\.?)\.?\s*\d+",
    re.I,
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

# UK NHS: 3-3-4 digit grouping
_NHS = re.compile(r"(?<!\d)\d{3}[\s\-]\d{3}[\s\-]\d{4}(?!\d)")

# Dates of birth (labelled)
_DOB_LABEL = re.compile(
    r"(?im)\b(?:dob|date\s+of\s+birth|born|geburtsdatum|birthdate)\b"
    r"[\s:.\-]*"
    r"(?P<val>\d{1,2}[\s./\-]\d{1,2}[\s./\-]\d{2,4}|\d{4}[\s./\-]\d{2}[\s./\-]\d{2})"
)

# Photo / video file references
_PHOTO_VIDEO_RE = re.compile(
    r"(?i)\b(?:passport\s+photo|photo\s+id|headshot|profile\s+(?:photo|picture|image)|"
    r"(?:photo|picture|image|video)\s+(?:attached|enclosed|of\s+the\s+(?:employee|person|applicant))|"
    r"\.(?:jpg|jpeg|png|gif|bmp|tiff?|mp4|mov|avi|mkv)\b)"
)

# Signature labels
_SIGNATURE_RE = re.compile(
    r"(?im)\b(?:signature|signed\s+by|unterschrift|signature\s+block)\b\s*[:\-]\s*(?P<val>.+?)\s*$"
)

# Travel history
_TRAVEL_RE = re.compile(
    r"(?i)\b(?:round[\-\s]trip|one[\-\s]way|itinerary|boarding\s+pass|"
    r"flight\s+[A-Z]{2}\d{2,4}|"
    r"travel(?:led|ling)?\s+to\s+[A-Z][a-z]+|trip\s+to\s+[A-Z][a-z]+|"
    r"[A-Z][a-z]+\s*(?:->|→)\s*[A-Z][a-z]+)"
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
_ADDRESS_RE = _label_value_re(r"address|home\s*address|anschrift|adresse|residence")
_BILLING_RE = _label_value_re(
    r"billing\s*address|shipping\s*address|invoice\s*address|delivery\s*address"
)

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
    }


def _looks_like_role(value: str) -> bool:
    tokens = [t.lower().strip(".") for t in value.split()]
    return bool(tokens) and all(t in _ROLE_STOPWORDS for t in tokens)


def _dedupe(findings: list[dict]) -> list[dict]:
    """Keep the longest finding per (category, overlapping span)."""
    by_cat: dict[str, list[dict]] = {}
    for f in findings:
        by_cat.setdefault(f["category"], []).append(f)

    kept: list[dict] = []
    for group in by_cat.values():
        group.sort(key=lambda x: x["start"])
        last_end = -1
        for f in group:
            if f["start"] >= last_end:
                kept.append(f)
                last_end = f["end"]
            elif f["end"] > last_end:
                kept[-1] = f
                last_end = f["end"]

    kept.sort(key=lambda x: (x["start"], x["category"]))
    return kept


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


def _detect_photo_video(text: str) -> list[dict]:
    out = []
    for m in _PHOTO_VIDEO_RE.finditer(text):
        f = _finding(PHOTO_VIDEO, m.start(), m.end(), m.group())
        if f:
            out.append(f)
    return out


def _detect_addresses(text: str) -> list[dict]:
    out = []
    for m in _BILLING_RE.finditer(text):
        f = _finding(BILLING_SHIPPING, m.start("val"), m.end("val"), m.group("val"))
        if f:
            out.append(f)
    for m in _ADDRESS_RE.finditer(text):
        f = _finding(HOME_ADDRESS, m.start("val"), m.end("val"), m.group("val"))
        if f:
            out.append(f)
    for rx in (_STREET_RE, _POSTAL_DE):
        for m in rx.finditer(text):
            f = _finding(HOME_ADDRESS, m.start(), m.end(), m.group())
            if f:
                out.append(f)
    return out

# module-level alias used by _detect_addresses above
_STREET_RE = _STREET


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


def _detect_travel(text: str) -> list[dict]:
    out = []
    for m in _TRAVEL_RE.finditer(text):
        f = _finding(TRAVEL_HISTORY, m.start(), m.end(), m.group())
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


def _detect_nhs(text: str) -> list[dict]:
    out = []
    for m in _NHS.finditer(text):
        v = m.group()
        # Exclude patterns already matched as SSN (different separator layout)
        if not re.fullmatch(r"\d{3}[\s\-]\d{2}[\s\-]\d{4}", v):
            f = _finding(NHS_NUMBER, m.start(), m.end(), v)
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
    photo_video: bool = True
    addresses: bool = True
    id_documents: bool = True
    travel: bool = True
    ip_addresses: bool = True
    credit_cards: bool = True
    iban: bool = True
    ssn: bool = True
    nhs: bool = True
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
        (cfg.photo_video,  _detect_photo_video),
        (cfg.addresses,    _detect_addresses),
        (cfg.id_documents, _detect_id_documents),
        (cfg.travel,       _detect_travel),
        (cfg.ip_addresses, _detect_ip_addresses),
        (cfg.credit_cards, _detect_credit_cards),
        (cfg.iban,         _detect_iban),
        (cfg.ssn,          _detect_ssn),
        (cfg.nhs,          _detect_nhs),
        (cfg.dob,          _detect_dob),
    ]

    findings: list[dict] = []
    for enabled, fn in runners:
        if enabled:
            findings.extend(fn(text))

    return _dedupe(findings)
