import json
import re
import traceback
import yaml
from pathlib import Path

from core.validator import filter_detections
OLLAMA_URL = "http://localhost:11434/api/generate"
def is_running() -> bool: return False
def first_model() -> str: return ""

CONFIG_DIR = Path(__file__).parent.parent / "config"

# LLM handles these — needs semantic understanding to avoid false positives
LLM_ENTITIES = {"PERSON", "LOCATION", "ORGANIZATION", "NRP"}

# Presidio handles these — pattern/regex is more reliable than LLM for structured data
PRESIDIO_ENTITIES = {
    "EMAIL_ADDRESS", "PHONE_NUMBER", "URL", "DATE_TIME",
    "IP_ADDRESS", "IBAN_CODE", "CREDIT_CARD", "MEDICAL_LICENSE",
    "US_SSN", "US_PASSPORT", "US_DRIVER_LICENSE", "ES_NIF",
    "IT_FISCAL_CODE", "UK_NHS", "AGE", "AU_ABN", "AU_ACN",
    "AU_TFN", "AU_MEDICARE",
}

LLM_DETECT_PROMPT = """You are a PII (Personal Identifiable Information) detector for GDPR compliance.

Scan the text below and extract ALL instances of these entity types: {entity_types}

Entity type definitions:
- PERSON: Real human names (first name, last name, full names). NOT titles, roles, diseases, organizations, SQL keywords, technical terms, or common nouns.
- LOCATION: Physical addresses, cities, countries, streets, postcodes. NOT generic terms like "hospital" or "department".
- ORGANIZATION: Company names, institution names, law firms, hospitals by name. NOT generic terms like "the hospital" or "the court".
- NRP: Nationality, religion, or political group mentions that identify a person.

Rules:
- Only extract ACTUAL PII, not generic terms or technical jargon
- "Dr. Smith" → PERSON (extract "Dr. Smith")
- "the patient" → NOT a person (generic noun)
- "DROP TABLE" → NOT a person (SQL keyword)
- "Blood Pressure" → NOT a person (medical term)
- Return ONLY valid JSON, no explanation

Return a JSON array of objects:
[{{"text": "exact text found", "type": "PERSON"}}, ...]

If no PII found, return: []

Text to scan:
---
{text}
---"""


_analyzer = None

def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }
        provider = NlpEngineProvider(nlp_configuration=config)
        nlp_engine = provider.create_engine()
        _analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
    return _analyzer


def load_level_entities(level: int) -> list[str]:
    with open(CONFIG_DIR / "levels.yaml") as f:
        config = yaml.safe_load(f)
    return config["levels"][level]["entities"]


def load_all_entity_info() -> dict:
    with open(CONFIG_DIR / "entities.yaml") as f:
        config = yaml.safe_load(f)
    return config["entities"]


def detect(
    text: str,
    entities: list[str],
    language: str = "en",
    model: str = "",
    engine: str = "both",
    score_threshold: float = 0.6,
) -> list[dict]:
    if not text.strip():
        return []

    detections = []

    llm_requested = [e for e in entities if e in LLM_ENTITIES]
    presidio_requested = [e for e in entities if e in PRESIDIO_ENTITIES]

    use_llm = engine in ("llm", "both")
    use_presidio = engine in ("presidio", "both")

    # default to all entities; narrowed down if LLM succeeds in "both" mode
    presidio_entities = list(entities)

    llm_used = False
    if use_llm and llm_requested and is_running():
        use_model = model or first_model()
        llm_detections = _llm_detect(text, llm_requested, model=use_model) if use_model else None
        if llm_detections is not None:
            detections += llm_detections
            llm_used = True
            if engine == "both":
                # LLM took the semantic ones, so Presidio only needs to cover structured
                presidio_entities = presidio_requested

    if use_presidio and presidio_entities:
        try:
            analyzer = _get_analyzer()
            results = analyzer.analyze(
                text=text,
                entities=presidio_entities,
                language=language,
                score_threshold=score_threshold,
            )
            for r in results:
                detections.append({
                    "entity_type": r.entity_type,
                    "start": r.start,
                    "end": r.end,
                    "score": round(r.score, 3),
                    "text": text[r.start:r.end],
                })
        except Exception as e:
            print(f"[pii_detector] Presidio error: {e}")

    # LLM-only mode but LLM wasn't available — fall back silently
    if engine == "llm" and not llm_used:
        print("[pii_detector] LLM unavailable, falling back to Presidio")
        try:
            analyzer = _get_analyzer()
            results = analyzer.analyze(
                text=text,
                entities=entities,
                language=language,
                score_threshold=score_threshold,
            )
            for r in results:
                detections.append({
                    "entity_type": r.entity_type,
                    "start": r.start,
                    "end": r.end,
                    "score": round(r.score, 3),
                    "text": text[r.start:r.end],
                })
        except Exception as e:
            print(f"[pii_detector] Presidio fallback error: {e}")

    detections.sort(key=lambda x: x["start"])
    detections = filter_detections(detections, text)
    return detections


def detect_with_level(text: str, level: int) -> list[dict]:
    return detect(text, load_level_entities(level))


def detect_with_custom(text: str, selected_entities: list[str]) -> list[dict]:
    return detect(text, selected_entities)


def summarize_detections(detections: list[dict]) -> dict:
    summary = {}
    for d in detections:
        t = d["entity_type"]
        summary[t] = summary.get(t, 0) + 1
    return summary


def _llm_detect(text: str, entity_types: list[str], model: str = "", max_chars: int = 6000) -> list[dict] | None:
    if not model:
        model = first_model()
    if not model:
        return None

    truncated = text[:max_chars]

    prompt = LLM_DETECT_PROMPT.format(
        entity_types=", ".join(entity_types),
        text=truncated,
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 2048,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        return _parse_llm_detections(raw, text)

    except Exception as e:
        print(f"[pii_detector] LLM detection failed: {e}")
        traceback.print_exc()
        return None


def _parse_llm_detections(raw: str, full_text: str) -> list[dict]:
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    start = raw.find("[")
    end = raw.rfind("]") + 1

    if start == -1 or end == 0:
        return []

    try:
        items = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return []

    detections = []
    for item in items:
        if not isinstance(item, dict):
            continue

        # different models use different key names
        found_text = (item.get("text") or item.get("pii_value") or item.get("value") or "").strip()
        entity_type = (item.get("type") or item.get("pii_type") or item.get("entity_type") or "").strip().upper()

        type_map = {"FULL NAME": "PERSON", "NAME": "PERSON", "STREET ADDRESS": "LOCATION",
                     "ADDRESS": "LOCATION", "GEOGRAPHIC ADDRESS": "LOCATION"}
        entity_type = type_map.get(entity_type, entity_type)

        if not found_text or not entity_type:
            continue

        # find all occurrences, not just the first one
        search_start = 0
        while True:
            idx = full_text.find(found_text, search_start)
            if idx == -1:
                idx = full_text.lower().find(found_text.lower(), search_start)
                if idx == -1:
                    break
                found_text = full_text[idx:idx + len(found_text)]

            detections.append({
                "entity_type": entity_type,
                "start": idx,
                "end": idx + len(found_text),
                "score": 0.85,
                "text": found_text,
            })
            search_start = idx + len(found_text)

    return detections
