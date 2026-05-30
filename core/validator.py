# post-processing filter — removes Presidio false positives common in medical/legal text

import re


MEDICAL_TERMS = {
    "covid", "covid-19", "sars", "sars-cov-2", "mers", "hiv", "aids",
    "hbv", "hcv", "ebola", "mpox", "monkeypox", "tuberculosis", "tb",
    "alzheimer", "alzheimer's", "parkinson", "parkinson's", "dementia",
    "diabetes", "cancer", "leukemia", "epilepsy", "asthma", "copd",
    "adhd", "ptsd", "ocd", "asd", "ms", "als",
    "influenza", "measles", "mumps", "rubella", "hepatitis",
    "biontech", "pfizer", "moderna", "astrazeneca", "janssen",
    "metformin", "ibuprofen", "paracetamol", "amoxicillin", "levodopa",
    "insulin", "aspirin", "penicillin", "omeprazole", "atorvastatin",
}

ORG_KEYWORDS = {
    "hospital", "clinic", "centre", "center", "institute", "university",
    "college", "school", "court", "tribunal", "council", "authority",
    "agency", "department", "ministry", "office", "foundation",
    "association", "society", "committee", "commission",
    "ltd", "limited", "llc", "inc", "incorporated", "plc", "gmbh",
    "ag", "sa", "bv", "nv", "sarl", "srl",
    "klinikum", "krankenhaus", "praxis", "kanzlei", "gericht",
    "bundesamt", "landesamt", "ministerium",
    "hôpital", "clinique", "tribunal", "ospedale", "clinica",
}

REGULATORY_ACRONYMS = {
    "gdpr", "hipaa", "ccpa", "dpa", "nhs", "gmc", "bma", "ama",
    "who", "ema", "fda", "nice", "cdc", "ecj", "echr",
    "eu", "un", "nato", "oecd",
}

# field labels that spaCy misclassifies as names
FIELD_LABEL_WORDS = {
    "tel", "fax", "ref", "mr", "mrs", "ms", "dr", "prof",
    "date", "time", "subject", "re", "cc", "bcc", "attn",
    # German
    "geburtsdatum", "antragsteller", "name", "vorname", "nachname",
    "adresse", "datum", "unterschrift", "stempel",
    # French
    "nom", "prénom", "adresse", "date", "signature",
    # Italian / Spanish
    "nombre", "firma", "fecha", "dirección",
}

# patterns that get dragged into the span boundary ("Anna Müller\nDOB:" → strip after \n)
STRUCTURAL_SUFFIX = re.compile(
    r"[\n\r]+.*$"  # everything after first newline
    r"|"
    r"\s*(DOB|D\.O\.B|Date of Birth|No\.|No:|Ref[.:]|ID[.:]|NHS|GMC|NPI|"
    r"MRN|Case|File|Born|Sex|Gender|Age|Room|Ward|Bed|Address|Email|Tel|"
    r"Phone|Fax|Subject|Date)[:\s#]*$",
    re.IGNORECASE | re.DOTALL,
)

STRUCTURAL_PREFIX = re.compile(
    r"^(Patient|Name|Client|Full Name|Defendant|Plaintiff|Claimant|"
    r"Subject|Re:|Dear|Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)[\s:]+",
    re.IGNORECASE,
)

TRAILING_PHONE_FRAGMENT = re.compile(r"\s+\+\d{1,3}$")

LEGAL_REFERENCE = re.compile(
    r"^(Article|Section|Clause|Schedule|Annex|Exhibit|Chapter|Part|Paragraph)\s+\d",
    re.IGNORECASE,
)

DRUG_DOSE = re.compile(r"\d+\s?(mg|ml|mcg|iu|g)\b", re.IGNORECASE)


def filter_detections(detections: list[dict], full_text: str) -> list[dict]:
    cleaned = []
    for det in detections:
        result = _process(det, full_text)
        if result is not None:
            cleaned.append(result)
    return _deduplicate(cleaned)


def _process(det: dict, full_text: str) -> dict | None:
    entity_type = det["entity_type"]
    text = det["text"].strip()
    score = det["score"]

    text = _clean_span(text)
    if not text.strip():
        return None

    lower = text.lower().strip()

    if LEGAL_REFERENCE.match(text):
        return None

    if entity_type == "PERSON":
        if not _valid_person(text, lower, score):
            return None

    elif entity_type == "NRP":
        if not _valid_nrp(text, lower):
            return None

    elif entity_type == "ORGANIZATION":
        lower_parts = [p.strip().lower() for p in re.split(r"[,;/]", text)]
        if all(_is_medical(p) or _is_regulatory(p) or not p for p in lower_parts):
            return None
        if _is_medical(lower) or _is_regulatory(lower):
            return None
        # Filter if the span starts with a regulatory acronym (e.g. "GDPR Article 9")
        first_word = lower.split()[0] if lower.split() else ""
        if _is_regulatory(first_word):
            return None
        # Filter if it's a legal reference with a regulatory prefix
        if LEGAL_REFERENCE.match(text):
            return None

    elif entity_type == "DATE_TIME":
        if re.match(r"^\d{4}$", text.strip()) and score < 0.6:
            return None
        digits = re.sub(r"\s", "", text)
        if re.match(r"^\d{2,6}$", digits) and " " in text and score < 0.7:
            return None

    elif entity_type == "URL":
        if score < 0.55 and len(text) < 8:
            return None

    # update span boundaries if we trimmed the text
    if text != det["text"].strip():
        new = det.copy()
        new["text"] = text
        offset = det["text"].find(text)
        if offset >= 0:
            new["start"] = det["start"] + offset
            new["end"] = new["start"] + len(text)
        return new

    return det


def _valid_person(text: str, lower: str, score: float) -> bool:
    if len(text.strip()) <= 1:
        return False
    if lower in FIELD_LABEL_WORDS:
        return False

    if re.search(r"\d", text):  # codes aren't names
        return False
    if text.isupper() and len(text) <= 5:  # acronym like NHS or HIV
        return False
    if _is_medical(lower) or _is_regulatory(lower):
        return False
    words = set(lower.split())
    if words & ORG_KEYWORDS:  # "City Hospital" misclassified as PERSON
        return False
    if DRUG_DOSE.search(text):
        return False
    if " " not in text.strip() and score < 0.75:  # single-token names need higher confidence
        return False

    return True


def _valid_nrp(text: str, lower: str) -> bool:
    if _is_medical(lower) or _is_regulatory(lower):
        return False
    if re.search(r"\d", text):
        return False
    if "," in text:
        return False
    return True


def _clean_span(text: str) -> str:
    text = STRUCTURAL_SUFFIX.sub("", text)
    text = STRUCTURAL_PREFIX.sub("", text)
    text = TRAILING_PHONE_FRAGMENT.sub("", text)
    return text.strip()

def _is_medical(lower: str) -> bool:
    return lower in MEDICAL_TERMS or any(lower.startswith(m) for m in MEDICAL_TERMS)

def _is_regulatory(lower: str) -> bool:
    return lower in REGULATORY_ACRONYMS

def _deduplicate(detections: list[dict]) -> list[dict]:
    if not detections:
        return detections
    sorted_dets = sorted(detections, key=lambda x: x["start"])
    result = []
    last_end = -1
    for det in sorted_dets:
        if det["start"] >= last_end:
            result.append(det)
            last_end = det["end"]
        elif det["score"] > result[-1]["score"]:
            result[-1] = det
            last_end = det["end"]
    return result
