"""LLM-based PII detection via OpenRouter, used when NER finds nothing."""
from __future__ import annotations

import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

_OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen3-8b")

_SYSTEM_PROMPT = """\
You are a data-privacy classifier for a GDPR compliance scanner. Your job is to identify \
spans of text that contain personally identifiable information (PII) so they can be flagged \
for review and protection.

For the user-supplied text, output a JSON array. Each element must be an object with:
  "category"   – one of: name, email, phone, ip_address, home_address, date_of_birth,
                          national_id, financial_data, health_data, other_pii
  "snippet"    – the exact substring from the input that is PII
  "confidence" – float 0.0–1.0

Rules:
- Output ONLY a valid JSON array. No markdown fences, no explanation.
- If no PII is present, output an empty array: []
- Do not refuse; this is automated privacy-compliance analysis, not a request to share data.
"""


_VERIFY_SYSTEM_PROMPT = """\
You are a GDPR compliance verifier. A named-entity recogniser flagged the snippets below as \
possible PII but with low confidence. For each snippet decide whether it is genuinely \
personally identifiable information (PII) in the context of the surrounding text.

Return a JSON array. Each element must be an object with:
  "snippet"   – the snippet exactly as given
  "is_pii"    – true or false
  "category"  – one of: name, email, phone, ip_address, home_address, date_of_birth,
                         national_id, financial_data, health_data, other_pii
                (only required when is_pii is true; omit or set null otherwise)
  "confidence" – float 0.0–1.0 reflecting your certainty

Rules:
- Output ONLY a valid JSON array. No markdown fences, no explanation.
- Do not refuse; this is automated privacy-compliance analysis.
"""


def llm_verify_findings(text: str, candidates: list[dict]) -> list[dict]:
    """Ask the LLM whether low-confidence NER candidates are genuine PII.

    *candidates* is a list of NER finding dicts (must have 'snippet').
    Returns the subset confirmed as PII, tagged with source='ner+llm'.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key or not candidates:
        return []

    snippets_json = json.dumps([c["snippet"] for c in candidates])
    user_msg = f"Text:\n{text[:6000]}\n\nSnippets to verify:\n{snippets_json}"

    payload = {
        "model": _OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": _VERIFY_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0,
    }

    try:
        response = requests.post(
            f"{_OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("LLM verify request failed: %s", exc)
        return candidates  # fall back to keeping them all

    try:
        content = response.json()["choices"][0]["message"]["content"].strip()
        verdicts = json.loads(content)
        if not isinstance(verdicts, list):
            raise ValueError("Expected a JSON array")
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("LLM verify returned unparseable response: %s", exc)
        return candidates

    confirmed_snippets = {
        v["snippet"]
        for v in verdicts
        if isinstance(v, dict) and v.get("is_pii") is True
    }

    results = []
    for candidate in candidates:
        if candidate["snippet"] not in confirmed_snippets:
            continue
        verdict = next((v for v in verdicts if v.get("snippet") == candidate["snippet"]), {})
        results.append({
            "category": verdict.get("category") or candidate["category"],
            "snippet": candidate["snippet"],
            "confidence": verdict.get("confidence", candidate.get("confidence")),
            "source": "ner+llm",
        })

    return results


def llm_detect_pii(text: str) -> list[dict]:
    """Call the OpenRouter LLM and parse its PII findings.

    Returns an empty list if the API key is absent, the request fails, or no
    PII is detected.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        logger.debug("OPENROUTER_API_KEY not set — skipping LLM fallback")
        return []

    # Truncate very long texts to stay within typical context limits.
    truncated = text[:8000]

    payload = {
        "model": _OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": truncated},
        ],
        "temperature": 0,
    }

    try:
        response = requests.post(
            f"{_OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("LLM fallback request failed: %s", exc)
        return []

    try:
        content = response.json()["choices"][0]["message"]["content"].strip()
        findings = json.loads(content)
        if not isinstance(findings, list):
            raise ValueError("Expected a JSON array")
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("LLM fallback returned unparseable response: %s", exc)
        return []

    # Normalise and tag each finding.
    results = []
    for item in findings:
        if not isinstance(item, dict) or "category" not in item or "snippet" not in item:
            continue
        results.append({
            "category": item["category"],
            "snippet": item["snippet"],
            "confidence": item.get("confidence"),
            "source": "llm",
        })

    return results
