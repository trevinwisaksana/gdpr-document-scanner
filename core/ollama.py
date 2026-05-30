# shared Ollama helpers used by all stages

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
_TAGS_URL = "http://localhost:11434/api/tags"


def is_running() -> bool:
    try:
        r = requests.get(_TAGS_URL, timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        r = requests.get(_TAGS_URL, timeout=5)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def first_model() -> str:
    models = list_models()
    return models[0] if models else ""
