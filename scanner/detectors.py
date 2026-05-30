"""Deterministic-first detection for the 13 GDPR categories.

Cheap, reproducible regex + label-proximity detectors run on every file; the spaCy/Presidio
NER engine (reused from core.pii_detector) supplies names and locations. An LLM is only
consulted for low-confidence/ambiguous spans, and only if explicitly enabled — see escalate.py.

Each detector yields dicts: {category, start, end, snippet, confidence, detector}. IDs and
ordering are deterministic so repeated scans on identical text produce identical findings.
"""
from __future__ import annotations

import re
from typing import Optional

from core.pii_detector import detect as ner_detect
from scanner import gdpr

# ── primitive patterns ────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\w)(?:\+\d{1,3}[\s./-]?)?(?:\(?\d{2,5}\)?[\s./-]?){2,5}\d{2,}(?!\w)")
POSTAL_DE_RE = re.compile(r"\b\d{5}[ \t]+[A-ZÄÖÜ][a-zäöüß]+")
STREET_RE = re.compile(r"\b[A-ZÄÖÜ][a-zäöüß.]+(?:str\.?|straße|gasse|weg|allee|platz)\.?\s*\d+", re.I)

# value token after an ID-style label — stays on one line (no newline in the class)
_ID_TOKEN = r"([A-Za-z]{0,3}[\- ]?[A-Za-z0-9][A-Za-z0-9\-/.]{2,})"

# words that look like name values but are roles / org units, not persons
_ROLE_STOPWORDS = {
    "lead", "team", "desk", "service", "ops", "governance", "manager", "reviewer",
    "approver", "participant", "owner", "trainer", "department", "it", "hr",
    "procurement", "operations", "support", "admin", "staff", "group", "office",
    "compliance", "officer", "identity", "access", "vendor", "management",
    "facility", "coordinator", "catalog", "unit", "committee", "board",
}


def _line_value(label_pat: str, text: str) -> list[re.Match]:
    """Match 'Label: value' to end of line. label_pat is an alternation of keywords."""
    rx = re.compile(rf"(?im)\b(?:{label_pat})\b\s*[:\-]\s*(?P<val>.+?)\s*$")
    return list(rx.finditer(text))


def _add(out: list, category: str, start: int, end: int, snippet: str,
         confidence: float, detector: str) -> None:
    snippet = snippet.strip()
    if not snippet or len(snippet) > 200:
        return
    if not re.search(r"[A-Za-z0-9]", snippet):
        return  # blank form fields ("______"), punctuation-only — not real data
    out.append({
        "category": category, "start": start, "end": end,
        "snippet": snippet, "confidence": round(confidence, 3), "detector": detector,
    })


# ── individual deterministic detectors ────────────────────────────────────────

def _emails(text: str, out: list) -> None:
    for m in EMAIL_RE.finditer(text):
        _add(out, gdpr.EMAIL, m.start(), m.end(), m.group(), 0.98, "regex")


def _phones_faxes(text: str, out: list) -> None:
    for m in _line_value(r"fax|fax\s*number|telefax", text):
        v = m.group("val")
        if re.search(r"\d", v):
            _add(out, gdpr.FAX, m.start("val"), m.end("val"), v, 0.95, "regex")
    for m in _line_value(r"phone|telephone|tel|mobile|mobil|cell|telefon", text):
        v = m.group("val")
        if re.search(r"\d", v):
            _add(out, gdpr.PHONE, m.start("val"), m.end("val"), v, 0.95, "regex")


def _signatures(text: str, out: list) -> None:
    for m in _line_value(r"signature|signed\s*by|unterschrift|signature\s*block", text):
        _add(out, gdpr.SIGNATURE, m.start("val"), m.end("val"), m.group("val"), 0.9, "regex")


def _photo_video(text: str, out: list) -> None:
    rx = re.compile(
        r"(?i)\b(passport\s+photo|photo\s+id|headshot|profile\s+(?:photo|picture|image)|"
        r"(?:photo|picture|image|video)\s+(?:attached|enclosed|of\s+the\s+(?:employee|person|applicant))|"
        r"\.(?:jpg|jpeg|png|mp4|mov)\b)")
    for m in rx.finditer(text):
        _add(out, gdpr.PHOTO_VIDEO, m.start(), m.end(), m.group(), 0.8, "regex")


def _id_documents(text: str, out: list) -> None:
    for label, cat, conf in [
        (r"passport(?:\s*(?:no\.?|number))?|reisepass", gdpr.PASSPORT, 0.95),
        (r"driver'?s?\s*licen[cs]e(?:\s*(?:no\.?|number))?|f[üu]hrerschein", gdpr.DRIVERS_LICENSE, 0.95),
        (r"id\s*card(?:\s*(?:no\.?|number))?|identity\s*card|personalausweis|ausweis(?:nummer)?|tax\s*id|vat\s*id", gdpr.ID_CARD, 0.9),
    ]:
        rx = re.compile(rf"(?im)\b(?:{label})\b\s*[:\-]?\s*(?P<val>{_ID_TOKEN})", re.I)
        for m in rx.finditer(text):
            v = m.group("val")
            if re.search(r"\d", v):
                _add(out, cat, m.start("val"), m.end("val"), v, conf, "regex")


def _usernames(text: str, out: list) -> None:
    for m in _line_value(r"username|user\s*name|login|user\s*id|account", text):
        _add(out, gdpr.USERNAME, m.start("val"), m.end("val"), m.group("val"), 0.9, "regex")
    # employee IDs like "(E-20491)" or "Employee ID: 20491"
    for m in re.finditer(r"\b[A-Z]-\d{4,6}\b", text):
        _add(out, gdpr.USERNAME, m.start(), m.end(), m.group(), 0.85, "regex")


def _addresses(text: str, out: list) -> None:
    for m in _line_value(r"billing\s*address|shipping\s*address|invoice\s*address|delivery\s*address", text):
        _add(out, gdpr.BILLING_SHIPPING, m.start("val"), m.end("val"), m.group("val"), 0.9, "regex")
    for m in _line_value(r"address|home\s*address|anschrift|adresse|residence", text):
        _add(out, gdpr.HOME_ADDRESS, m.start("val"), m.end("val"), m.group("val"), 0.88, "regex")
    # free-standing street / postal patterns not behind a label
    for rx in (STREET_RE, POSTAL_DE_RE):
        for m in rx.finditer(text):
            _add(out, gdpr.HOME_ADDRESS, m.start(), m.end(), m.group(), 0.7, "regex")


def _travel(text: str, out: list) -> None:
    rx = re.compile(
        r"(?i)\b(round[\- ]trip|one[\- ]way|itinerary|boarding\s+pass|"
        r"flight\s+[A-Z]{2}\d{2,4}|"
        r"travel(?:led|ling)?\s+to\s+[A-Z][a-z]+|trip\s+to\s+[A-Z][a-z]+|"
        r"[A-Z][a-z]+\s*(?:->|→)\s*[A-Z][a-z]+)")
    for m in rx.finditer(text):
        _add(out, gdpr.TRAVEL_HISTORY, m.start(), m.end(), m.group(), 0.7, "regex")


# labels whose value is a person's name
_NAME_LABELS = (r"name|employee|participant|manager|reviewer|approver|trainer|"
                r"contact\s*person|owner|requested\s*by|prepared\s*by|applicant")

def _looks_like_role(v: str) -> bool:
    tokens = [t.lower().strip(".") for t in v.split()]
    return bool(tokens) and all(t in _ROLE_STOPWORDS for t in tokens)


def _names(text: str, out: list) -> None:
    # label-based names are highly reliable in form documents.
    # Separator is [ \t] (not \s) so a value never bleeds into the next line.
    name_spans: set[tuple[int, int]] = set()
    rx = re.compile(rf"(?im)\b(?:{_NAME_LABELS})\b[ \t]*[:\-][ \t]*(?P<val>[A-Z][\w.'-]+(?:[ \t]+[A-Z][\w.'-]+){{0,3}})")
    for m in rx.finditer(text):
        v = m.group("val").strip()
        if "@" in v or re.search(r"\d", v) or _looks_like_role(v):
            continue
        _add(out, gdpr.NAME, m.start("val"), m.end("val"), v, 0.95, "regex")
        name_spans.add((m.start("val"), m.end("val")))

    # spaCy/Presidio NER for names the labels miss
    try:
        for d in ner_detect(text, ["PERSON"], engine="presidio"):
            span = (d["start"], d["end"])
            if any(not (span[1] <= s or e <= span[0]) for s, e in name_spans):
                continue
            if _looks_like_role(d["text"]) or " " not in d["text"].strip():
                continue  # roles and bare single tokens are usually field labels, not names
            _add(out, gdpr.NAME, d["start"], d["end"], d["text"], min(d["score"], 0.9), "spacy")
    except Exception as e:  # NER is best-effort; deterministic detectors stand alone
        print(f"[detectors] NER unavailable: {e}")


# ── orchestration ─────────────────────────────────────────────────────────────

def _dedupe(dets: list[dict]) -> list[dict]:
    """One finding per (category, overlapping-span); keep the highest confidence.
    Deterministic: sort by (start, category) so reruns are identical."""
    by_cat: dict[str, list[dict]] = {}
    for d in dets:
        by_cat.setdefault(d["category"], []).append(d)
    kept: list[dict] = []
    for cat, group in by_cat.items():
        group.sort(key=lambda x: (x["start"], -x["confidence"]))
        last_end = -1
        for d in group:
            if d["start"] >= last_end:
                kept.append(d)
                last_end = d["end"]
            elif kept and d["confidence"] > kept[-1]["confidence"]:
                kept[-1] = d
                last_end = d["end"]
    kept.sort(key=lambda x: (x["start"], x["category"]))
    return kept


def detect_categories(text: str, escalate_fn: Optional[callable] = None) -> list[dict]:
    """Run all detectors over text and return GDPR findings (with articles attached)."""
    if not text.strip():
        return []
    out: list[dict] = []
    _names(text, out)
    _emails(text, out)
    _phones_faxes(text, out)
    _signatures(text, out)
    _photo_video(text, out)
    _id_documents(text, out)
    _usernames(text, out)
    _addresses(text, out)
    _travel(text, out)

    findings = _dedupe(out)

    if escalate_fn is not None:
        for f in findings:
            if f["confidence"] < 0.75:
                verdict = escalate_fn(text, f)
                if verdict is not None:
                    f["confidence"], f["detector"] = verdict, "llm"

    for f in findings:
        f["gdpr_articles"] = gdpr.articles_for(f["category"])
    return findings
