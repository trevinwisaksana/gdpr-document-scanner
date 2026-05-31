"""
Test all three detection paths (regex, NER, LLM) against synthetic PDFs.

Creates 3 PDFs in /tmp:
  - regex_pii.pdf    — email, phone, SSN, credit card → caught by regex
  - ner_pii.pdf      — person names + address, no regex patterns → caught by NER
  - llm_pii.pdf      — implicit health/case data, no names/patterns → caught by LLM

Usage:
  python test_detectors.py
"""
from __future__ import annotations

import logging
import sys
import textwrap
from pathlib import Path

import fitz  # pymupdf
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

import time
from app.process import scan_document, ScanResult
from scanner import store, gdpr

# ── PDF content for each detection path ───────────────────────────────────────

REGEX_TEXT = textwrap.dedent("""\
    Employee Payroll Record

    The following data is processed for payroll purposes only.

    Contact Email:  alice.martin@company-corp.com
    Work Phone:     +44 7911 123456
    SSN:            378-82-9120
    Credit Card:    4111 1111 1111 1111

    This record is confidential and subject to GDPR Article 88.
""")

NER_TEXT = textwrap.dedent("""\
    Staff Directory — Engineering Department

    The department is managed by James Robertson, who reports to
    Patricia Chen (VP of Technology). New joiners should contact
    the onboarding team at the London office located at
    12 Baker Street, London, England.

    All staff are subject to the company's data retention policy.
    No contact details or identifiers are listed in this excerpt.
""")

LLM_TEXT = textwrap.dedent("""\
    Internal Welfare Assessment — Strictly Confidential

    This assessment was conducted at the request of the regional compliance
    office following a referral by the social care team. The household
    income falls below the assistance threshold, with monthly outgoings
    exceeding declared income by several hundred euros.

    Medical history on file indicates a diagnosis of a chronic cardiac
    condition first recorded in early childhood, with ongoing treatment
    at a private clinic. The record also notes a history of psychiatric
    care documented across multiple facility visits over recent years.

    The data held constitutes special category health and financial data
    under Article nine of the GDPR regulation. Recommend escalation to
    the data protection officer for review before further processing.

    This report contains no names, identifiers, phone numbers, email
    addresses, or numeric codes — only inferred personal circumstances.
""")

TESTS = [
    ("regex_pii.pdf", REGEX_TEXT,  "regex"),
    ("ner_pii.pdf",   NER_TEXT,    "ner"),
    ("llm_pii.pdf",   LLM_TEXT,    "llm"),
]


def make_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 60), text, fontsize=11, fontname="helv")
    doc.save(str(path))
    doc.close()


def _col(value: str, width: int) -> str:
    return value[:width].ljust(width)


def print_findings_table(results: list[tuple[str, str, ScanResult]]) -> None:
    # ── per-finding detail table ───────────────────────────────────────────────
    C = {"file": 20, "detector": 10, "category": 16, "conf": 6}
    sep = "+" + "+".join("-" * (w + 2) for w in C.values()) + "+"
    hdr = "| " + " | ".join(k.upper().ljust(w) for k, w in C.items()) + " |"

    print(sep)
    print(hdr)
    print(sep)

    for filename, _expected, result in results:
        for f in result.findings:
            conf_raw = f.get("confidence")
            conf = f"{conf_raw:.2f}" if conf_raw is not None else "—"
            print(
                "| "
                + " | ".join([
                    _col(filename, C["file"]),
                    _col(f.get("source", "?"), C["detector"]),
                    _col(f.get("category", "?"), C["category"]),
                    conf.ljust(C["conf"]),
                ])
                + " |"
            )
        print(sep)

    # ── summary table ─────────────────────────────────────────────────────────
    print()
    SC = {"file": 20, "expected": 10, "detector": 14, "categories": 36, "status": 6}
    ssep = "+" + "+".join("-" * (w + 2) for w in SC.values()) + "+"
    shdr = (
        "| "
        + " | ".join(k.upper().ljust(w) for k, w in SC.items())
        + " |"
    )

    print(ssep)
    print(shdr)
    print(ssep)

    for filename, expected, result in results:
        if not result.has_pii:
            detector = "none"
            categories = "—"
            status = "MISS"
        else:
            sources = {f.get("source", "?") for f in result.findings}
            detector = ", ".join(sorted(sources))
            categories = ", ".join(sorted({f.get("category", "?") for f in result.findings}))
            dominant = max(sources, key=lambda s: sum(1 for f in result.findings if f.get("source") == s))
            status = "PASS" if (expected in dominant or dominant in expected) else "WARN"

        print(
            "| "
            + " | ".join([
                _col(filename, SC["file"]),
                _col(expected, SC["expected"]),
                _col(detector, SC["detector"]),
                _col(categories, SC["categories"]),
                status.ljust(SC["status"]),
            ])
            + " |"
        )

    print(ssep)


def _to_store_findings(result: ScanResult, path: Path) -> list[dict]:
    """Convert ScanResult findings to the shape store.replace_findings expects."""
    out = []
    for i, f in enumerate(result.findings):
        out.append({
            "category":     f["category"],
            "start":        f.get("start", i),
            "end":          f.get("end", i + 1),
            "snippet":      f.get("snippet", ""),
            "confidence":   f.get("confidence") or 0.0,
            "detector":     f.get("source", "unknown"),
            "gdpr_articles": gdpr.articles_for(f["category"]),
        })
    return out


if __name__ == "__main__":
    tmp = Path("/tmp/gdpr_test_pdfs")
    tmp.mkdir(exist_ok=True)

    for name, text, _ in TESTS:
        make_pdf(tmp / name, text)

    for name, _, expected in TESTS:
        pdf = tmp / name
        result = scan_document(pdf)

        # persist to DB
        stat = pdf.stat()
        fid = store.upsert_file(str(pdf), "fileshare", stat.st_size, stat.st_mtime, None, None)
        store.replace_findings(fid, _to_store_findings(result, pdf))
        store.mark_scanned(fid, time.time())

        print(f"\n{name}")
        for f in result.findings:
            conf = f"{f['confidence']:.2f}" if f.get("confidence") else "—"
            print(f"  [{f['source']}] {f['category']}  conf={conf}")
