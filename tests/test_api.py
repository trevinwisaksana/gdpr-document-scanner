"""Tests for the FastAPI scan endpoint."""
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from app.main import app
from app.process import ScanResult


client = TestClient(app)


def _make_row(**kwargs):
    """Return a dict-like object that supports row["key"] access, mimicking sqlite3.Row."""
    row = MagicMock()
    row.__getitem__ = lambda self, k: kwargs[k]
    return row


def test_list_flagged_files_returns_404_for_unknown_user():
    with patch("app.main.store.get_user", return_value=None):
        response = client.get("/users/nonexistent/files")
    assert response.status_code == 404
    assert response.json()["detail"] == "user not found"


def test_list_flagged_files_returns_files_with_findings():
    fake_user = _make_row(id="u-1", name="Alice", email="alice@example.com", role="employee")
    fake_files = [
        _make_row(
            id="f-1",
            path="docs/contract.pdf",
            source_type="onedrive",
            size_bytes=12000,
            last_modified=1717000000.0,
            last_scanned_at=1717100000.0,
            n_findings=3,
            categories="email,phone",
        ),
        _make_row(
            id="f-2",
            path="docs/hr.docx",
            source_type="sharepoint",
            size_bytes=8000,
            last_modified=1716000000.0,
            last_scanned_at=1716100000.0,
            n_findings=1,
            categories="name",
        ),
    ]

    with (
        patch("app.main.store.get_user", return_value=fake_user),
        patch("app.main.store.flagged_files_for_user", return_value=fake_files),
    ):
        response = client.get("/users/u-1/files")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "u-1"
    assert body["total"] == 2
    assert body["files"][0]["id"] == "f-1"
    assert body["files"][0]["n_findings"] == 3
    assert set(body["files"][0]["finding_categories"]) == {"email", "phone"}
    assert body["files"][1]["finding_categories"] == ["name"]


def test_list_flagged_files_returns_empty_list_when_no_findings():
    fake_user = _make_row(id="u-2", name="Bob", email="bob@example.com", role="employee")

    with (
        patch("app.main.store.get_user", return_value=fake_user),
        patch("app.main.store.flagged_files_for_user", return_value=[]),
    ):
        response = client.get("/users/u-2/files")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["files"] == []


def test_list_flagged_files_handles_null_categories():
    fake_user = _make_row(id="u-3", name="Carol", email="carol@example.com", role="employee")
    fake_files = [
        _make_row(
            id="f-3",
            path="docs/empty.pdf",
            source_type="fileshare",
            size_bytes=500,
            last_modified=1715000000.0,
            last_scanned_at=None,
            n_findings=0,
            categories=None,
        ),
    ]

    with (
        patch("app.main.store.get_user", return_value=fake_user),
        patch("app.main.store.flagged_files_for_user", return_value=fake_files),
    ):
        response = client.get("/users/u-3/files")

    assert response.status_code == 200
    assert response.json()["files"][0]["finding_categories"] == []


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


def test_kpi_total_files_registered_endpoint():
    with patch("app.main.total_files_registered", return_value=42):
        response = client.get("/kpis/total-files-registered")

    assert response.status_code == 200
    assert response.json() == {"value": 42}


def test_kpi_total_files_flagged_endpoint():
    with patch("app.main.total_files_flagged", return_value=9):
        response = client.get("/kpis/total-files-flagged")

    assert response.status_code == 200
    assert response.json() == {"value": 9}


def test_kpi_total_files_processed_endpoint():
    with patch("app.main.total_files_processed", return_value=37):
        response = client.get("/kpis/total-files-processed")

    assert response.status_code == 200
    assert response.json() == {"value": 37}


def test_kpi_percentage_files_flagged_endpoint():
    with patch("app.main.percentage_files_flagged", return_value=24.32):
        response = client.get("/kpis/percentage-files-flagged")

    assert response.status_code == 200
    assert response.json() == {"value": 24.32}


def test_kpi_owners_endpoint():
    with patch("app.main.list_all_owners", return_value=["a@example.com", "b@example.com"]):
        response = client.get("/kpis/owners")

    assert response.status_code == 200
    assert response.json() == {"owners": ["a@example.com", "b@example.com"]}


def test_kpi_flagged_files_per_owner_endpoint():
    with patch(
        "app.main.flagged_files_per_owner",
        return_value=[
            {"owner": "a@example.com", "flagged_files": 7},
            {"owner": "b@example.com", "flagged_files": 2},
        ],
    ):
        response = client.get("/kpis/flagged-files-per-owner")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"owner": "a@example.com", "flagged_files": 7},
            {"owner": "b@example.com", "flagged_files": 2},
        ]
    }


def test_drive_workflow_endpoint_queues_files_to_pubsub():
    files = [
        {"file_id": "f-1", "name": "alpha.pdf"},
        {"file_id": "f-2", "name": "beta.txt"},
    ]

    class FakeLister:
        def list_files(self):
            return iter(files)

    class FakePublisher:
        def __init__(self):
            self.published = []

        def publish(self, topic, data):
            self.published.append(data)

            class FakeFuture:
                def result(self_):
                    return None

            return FakeFuture()

    fake_publisher = FakePublisher()

    with (
        patch("app.main.GDriveLister", return_value=FakeLister()),
        patch("app.main._publisher", fake_publisher),
        patch.dict("os.environ", {"PUBSUB_TOPIC": "projects/test/topics/test"}),
    ):
        response = client.post("/workflows/drive/scan")

    assert response.status_code == 200
    body = response.json()
    assert body["files_queued"] == 2
    assert body["failed"] == 0
    assert body["status"] == "ok"
    assert len(fake_publisher.published) == 2
