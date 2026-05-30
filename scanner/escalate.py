"""Optional LLM escalation via OpenRouter for low-confidence findings.

OFF by default: if OPENROUTER_API_KEY is unset the whole pipeline runs deterministically,
which is what the demo uses. When enabled, only ambiguous spans are sent (not whole files),
at temperature 0, and verdicts are cached by content hash — keeping cost/compute minimal and
results reproducible (a re-scan never re-queries).
"""
from __future__ import annotations

import hashlib
import os
from typing import Callable, Optional

from scanner import gdpr

_CACHE: dict[str, float] = {}

_PROMPT = (
    "You verify whether a snippet is really personal data of category '{label}'.\n"
    "Snippet: {snippet!r}\n"
    "Reply with ONLY a number 0.0-1.0 = confidence it is genuine {label}."
)


def is_enabled() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY"))


def get_escalator() -> Optional[Callable[[str, dict], Optional[float]]]:
    """Return an escalation fn, or None when the LLM is disabled (deterministic-only)."""
    if not is_enabled():
        return None
    return _escalate


def _escalate(full_text: str, finding: dict) -> Optional[float]:
    key = hashlib.sha256(
        f"{finding['category']}:{finding['snippet']}".encode()
    ).hexdigest()
    if key in _CACHE:
        return _CACHE[key]

    verdict = _query(finding)
    if verdict is not None:
        _CACHE[key] = verdict
    return verdict


def _query(finding: dict) -> Optional[float]:
    import requests

    base = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    prompt = _PROMPT.format(label=gdpr.label(finding["category"]), snippet=finding["snippet"])

    try:
        r = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
            json={
                "model": model,
                "temperature": 0,
                "max_tokens": 8,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        return _parse_float(content)
    except Exception as e:
        print(f"[escalate] OpenRouter call failed: {e}")
        return None


def _parse_float(text: str) -> Optional[float]:
    import re
    m = re.search(r"[01](?:\.\d+)?", text)
    if not m:
        return None
    return max(0.0, min(1.0, float(m.group())))
