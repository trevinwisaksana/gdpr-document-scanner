"""Tests for the FastAPI scan endpoint."""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from app.main import app
from app.process import ScanResult


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_scan_text_endpoint_maps_payload_to_scanner():
    fake_result = ScanResult(
        file_path="invoice-1.txt",
        findings=[{"category": "email", "snippet": "user@example.com", "source": "regex"}],
    )

    with patch("app.main.scan_text", return_value=fake_result) as mock_scan:
        response = client.post(
            "/scan/text",
            json={
                "text": "Contact user@example.com",
                "file_id": "invoice-1.txt",
                "config": {"emails": True, "phones": False},
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "file_path": "invoice-1.txt",
        "findings": fake_result.findings,
        "has_pii": True,
    }
    mock_scan.assert_called_once()
    _, _, config = mock_scan.call_args.args
    assert config.emails is True
    assert config.phones is False


def test_drive_workflow_endpoint_runs_listing_download_and_scan():
    files = [
        {"file_id": "f-1", "name": "alpha.pdf", "mime_type": "application/pdf"},
        {"file_id": "f-2", "name": "beta.txt", "mime_type": "text/plain"},
    ]
    scan_results = [
        ScanResult(file_path="f-1", findings=[{"category": "email", "snippet": "a@b.com", "source": "regex"}]),
        ScanResult(file_path="f-2", findings=[]),
    ]

    class FakeLister:
        def list_files(self):
            return iter(files)

    class FakeDownloader:
        def download_and_extract(self, file_id, mime_type, file_name):
            return f"text-for-{file_id}-{mime_type}-{file_name}"

    with (
        patch("app.main.GDriveLister", return_value=FakeLister()) as mock_lister,
        patch("app.main.GDriveDownloader", return_value=FakeDownloader()) as mock_downloader,
        patch("app.main.scan_text", side_effect=scan_results) as mock_scan,
    ):
        response = client.post("/workflows/drive/scan", json={"max_files": 2})

    assert response.status_code == 200
    assert response.json() == {
        "listed_files": 2,
        "processed_files": 2,
        "with_pii": 1,
        "clean": 1,
        "results": [
            {
                "file_id": "f-1",
                "name": "alpha.pdf",
                "mime_type": "application/pdf",
                "has_pii": True,
                "findings": scan_results[0].findings,
            },
            {
                "file_id": "f-2",
                "name": "beta.txt",
                "mime_type": "text/plain",
                "has_pii": False,
                "findings": [],
            },
        ],
    }
    mock_lister.assert_called_once()
    mock_downloader.assert_called_once()
    assert mock_scan.call_count == 2
