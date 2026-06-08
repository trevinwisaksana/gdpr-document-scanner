"""Detector profiles — maps document type to RegexDetectorConfig.

Each profile enables only the detectors that are relevant for that document
type, so irrelevant regex passes are skipped. `generic` enables everything
and is the safe fallback used when classification confidence is low.
"""
from __future__ import annotations

from detectors.regex import RegexDetectorConfig

DETECTOR_PROFILES: dict[str, RegexDetectorConfig] = {
    "hr_form": RegexDetectorConfig(
        emails=True, phones=True, usernames=True, signatures=True,
        id_documents=True, ip_addresses=False, credit_cards=False,
        iban=False, ssn=True, dob=True,
    ),
    "invoice": RegexDetectorConfig(
        emails=True, phones=True, usernames=False, signatures=False,
        id_documents=False, ip_addresses=False, credit_cards=True,
        iban=True, ssn=False, dob=False,
    ),
    "contract": RegexDetectorConfig(
        emails=True, phones=True, usernames=False, signatures=True,
        id_documents=False, ip_addresses=False, credit_cards=False,
        iban=False, ssn=False, dob=False,
    ),
    "id_document": RegexDetectorConfig(
        emails=False, phones=False, usernames=True, signatures=False,
        id_documents=True, ip_addresses=False, credit_cards=False,
        iban=False, ssn=True, dob=True,
    ),
    "medical": RegexDetectorConfig(
        emails=True, phones=True, usernames=True, signatures=False,
        id_documents=True, ip_addresses=False, credit_cards=False,
        iban=False, ssn=True, dob=True,
    ),
    "correspondence": RegexDetectorConfig(
        emails=True, phones=True, usernames=False, signatures=True,
        id_documents=False, ip_addresses=False, credit_cards=False,
        iban=False, ssn=False, dob=False,
    ),
    "financial": RegexDetectorConfig(
        emails=True, phones=True, usernames=False, signatures=False,
        id_documents=False, ip_addresses=False, credit_cards=True,
        iban=True, ssn=False, dob=False,
    ),
    "generic": RegexDetectorConfig(),  # all detectors enabled
}


def profile_for(doc_type: str) -> RegexDetectorConfig:
    """Return the RegexDetectorConfig for doc_type, falling back to generic."""
    return DETECTOR_PROFILES.get(doc_type, DETECTOR_PROFILES["generic"])
