"""Unit tests for app/process.py — cron job orchestration."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from app.process import ScanResult, scan_document, process_file, run


# ── fixtures ──────────────────────────────────────────────────────────────────

PII_TEXT = "Contact john.doe@example.com or call +1-555-012-3456"
CLEAN_TEXT = "The quarterly report covers operational metrics."


@pytest.fixture
def txt_with_pii(tmp_path):
    p = tmp_path / "pii.txt"
    p.write_text(PII_TEXT)
    return p


@pytest.fixture
def txt_clean(tmp_path):
    p = tmp_path / "clean.txt"
    p.write_text(CLEAN_TEXT)
    return p


@pytest.fixture
def pdf_with_pii(tmp_path):
    import pymupdf

    p = tmp_path / "pii.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), PII_TEXT)
    doc.save(p)
    doc.close()
    return p


# ── ScanResult ────────────────────────────────────────────────────────────────

class TestScanResult:
    def test_has_pii_true_when_findings_present(self):
        result = ScanResult(file_path="f.txt", findings=[{"category": "email"}])
        assert result.has_pii is True

    def test_has_pii_false_when_findings_empty(self):
        result = ScanResult(file_path="f.txt", findings=[])
        assert result.has_pii is False

    def test_file_path_stored_as_string(self):
        result = ScanResult(file_path="/some/path.pdf", findings=[])
        assert result.file_path == "/some/path.pdf"


# ── scan_document ─────────────────────────────────────────────────────────────

class TestScanDocument:
    def test_returns_scan_result(self, txt_with_pii):
        result = scan_document(txt_with_pii)
        assert isinstance(result, ScanResult)

    def test_file_path_recorded(self, txt_with_pii):
        result = scan_document(txt_with_pii)
        assert result.file_path == str(txt_with_pii)

    def test_detects_pii_in_txt(self, txt_with_pii):
        result = scan_document(txt_with_pii)
        assert result.has_pii

    def test_no_findings_on_clean_file(self, txt_clean):
        result = scan_document(txt_clean)
        assert not result.has_pii

    def test_accepts_path_object(self, txt_with_pii):
        result = scan_document(Path(txt_with_pii))
        assert isinstance(result, ScanResult)

    def test_accepts_string_path(self, txt_with_pii):
        result = scan_document(str(txt_with_pii))
        assert isinstance(result, ScanResult)

    def test_detects_pii_in_pdf(self, pdf_with_pii):
        result = scan_document(pdf_with_pii)
        assert result.has_pii

    def test_findings_have_expected_keys(self, txt_with_pii):
        result = scan_document(txt_with_pii)
        for finding in result.findings:
            assert {"category", "snippet"} <= finding.keys()

    def test_config_disabling_all_detectors_returns_empty(self, txt_with_pii):
        from unittest.mock import patch
        from detectors.regex import RegexDetectorConfig

        cfg = RegexDetectorConfig(
            emails=False, phones=False, usernames=False,
            signatures=False, id_documents=False, ip_addresses=False,
            credit_cards=False, iban=False, ssn=False, dob=False,
        )
        with patch("app.process.ner_inference", return_value=[]), \
             patch("app.process.llm_detect_pii", return_value=[]):
            result = scan_document(txt_with_pii, config=cfg)
        assert result.findings == []

    def test_unsupported_file_type_raises(self, tmp_path):
        bad = tmp_path / "file.xyz"
        bad.write_text("irrelevant")
        with pytest.raises(ValueError, match="Unsupported file type"):
            scan_document(bad)


# ── process_file ──────────────────────────────────────────────────────────────

class TestProcessFile:
    def test_returns_scan_result(self, txt_with_pii):
        result = process_file(txt_with_pii)
        assert isinstance(result, ScanResult)

    def test_calls_handle_pii_found_when_pii_present(self, txt_with_pii):
        with patch("app.process.handle_pii_found") as mock_found, \
             patch("app.process.handle_no_pii") as mock_clean:
            process_file(txt_with_pii)
            mock_found.assert_called_once()
            mock_clean.assert_not_called()

    def test_calls_handle_no_pii_when_clean(self, txt_clean):
        with patch("app.process.handle_pii_found") as mock_found, \
             patch("app.process.handle_no_pii") as mock_clean:
            process_file(txt_clean)
            mock_clean.assert_called_once()
            mock_found.assert_not_called()

    def test_handler_receives_scan_result(self, txt_with_pii):
        with patch("app.process.handle_pii_found") as mock_found:
            result = process_file(txt_with_pii)
            mock_found.assert_called_once_with(result)


# ── run ───────────────────────────────────────────────────────────────────────

class TestRun:
    def test_returns_list(self, txt_with_pii):
        results = run([txt_with_pii])
        assert isinstance(results, list)

    def test_processes_all_files(self, txt_with_pii, txt_clean):
        results = run([txt_with_pii, txt_clean])
        assert len(results) == 2

    def test_result_paths_match_inputs(self, txt_with_pii, txt_clean):
        results = run([txt_with_pii, txt_clean])
        paths = {r.file_path for r in results}
        assert str(txt_with_pii) in paths
        assert str(txt_clean) in paths

    def test_empty_list_returns_empty(self):
        assert run([]) == []

    def test_bad_file_does_not_abort_run(self, tmp_path, txt_with_pii):
        bad = tmp_path / "missing.txt"  # does not exist
        results = run([bad, txt_with_pii])
        # bad file is skipped; good file still processed
        assert any(r.file_path == str(txt_with_pii) for r in results)
        assert len(results) == 1

    def test_bad_file_is_logged(self, tmp_path, caplog):
        import logging

        bad = tmp_path / "ghost.pdf"  # unsupported + missing
        with caplog.at_level(logging.ERROR):
            run([bad])
        assert caplog.records  # at least one error logged

    def test_summary_logged_after_run(self, txt_with_pii, txt_clean, caplog):
        import logging

        with caplog.at_level(logging.INFO):
            run([txt_with_pii, txt_clean])
        messages = [r.message for r in caplog.records]
        assert any("Scan complete" in m for m in messages)
