"""Tests for app/llm_fallback.py"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from unittest.mock import MagicMock, patch

import pytest

from app.detection.llm_fallback import llm_detect_pii


def _mock_response(content: str, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    resp.raise_for_status = MagicMock()
    if status >= 400:
        from requests import HTTPError
        resp.raise_for_status.side_effect = HTTPError(response=resp)
    return resp


class TestLlmDetectPii:
    def test_returns_empty_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        result = llm_detect_pii("John Smith lives at 10 Downing Street")
        assert result == []

    def test_parses_findings_correctly(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        # LLM prompt instructs the model NOT to return snippets, so payload has no snippet field
        payload = json.dumps([
            {"category": "name", "confidence": 0.95},
            {"category": "home_address", "confidence": 0.9},
        ])
        with patch("app.detection.llm_fallback.requests.post", return_value=_mock_response(payload)):
            findings = llm_detect_pii("John Smith lives at 10 Downing Street")

        assert len(findings) == 2
        assert findings[0] == {"category": "name", "confidence": 0.95, "source": "llm"}
        assert findings[1] == {"category": "home_address", "confidence": 0.9, "source": "llm"}

    def test_all_findings_tagged_with_source_llm(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        payload = json.dumps([{"category": "email", "snippet": "a@b.com", "confidence": 0.99}])
        with patch("app.detection.llm_fallback.requests.post", return_value=_mock_response(payload)):
            findings = llm_detect_pii("email a@b.com")

        assert all(f["source"] == "llm" for f in findings)

    def test_returns_empty_on_network_error(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        import requests as req
        with patch("app.detection.llm_fallback.requests.post", side_effect=req.ConnectionError("offline")):
            result = llm_detect_pii("some text")
        assert result == []

    def test_returns_empty_on_http_error(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        with patch("app.detection.llm_fallback.requests.post", return_value=_mock_response("", status=401)):
            result = llm_detect_pii("some text")
        assert result == []

    def test_returns_empty_when_llm_returns_empty_array(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        with patch("app.detection.llm_fallback.requests.post", return_value=_mock_response("[]")):
            result = llm_detect_pii("The quarterly report covers operational metrics.")
        assert result == []

    def test_skips_malformed_findings(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        payload = json.dumps([
            {"snippet": "no category"},
            {"category": "name", "snippet": "Alice"},
        ])
        with patch("app.detection.llm_fallback.requests.post", return_value=_mock_response(payload)):
            findings = llm_detect_pii("Alice")
        assert len(findings) == 1
        assert findings[0]["category"] == "name"

    def test_returns_empty_on_non_json_response(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        with patch("app.detection.llm_fallback.requests.post", return_value=_mock_response("not json at all")):
            result = llm_detect_pii("some text")
        assert result == []

    @pytest.mark.integration
    def test_live_llm_detects_pii(self):
        """Calls the real OpenRouter API — requires OPENROUTER_API_KEY in env."""
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        findings = llm_detect_pii("Please contact Sarah Connor at sarah.connor@skynet.io or +44 7700 900123.")
        assert len(findings) > 0
        for f in findings:
            assert "category" in f
            assert "snippet" in f
            assert f["source"] == "llm"
