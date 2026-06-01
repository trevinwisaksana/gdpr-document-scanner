"""Tests for KPI history helpers."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.KPR_functions import (
    percentage_files_flagged_over_time,
    total_files_flagged_over_time,
    total_files_over_time,
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_total_files_over_time_returns_rows_ordered_by_first_column():
    rows = [
        ("2026-01-01T10:00:00Z", 12),
        ("2026-01-02T10:00:00Z", 18),
    ]
    cursor = FakeCursor(rows)
    conn = FakeConnection(cursor)
    fake_psycopg2 = MagicMock(connect=MagicMock(return_value=conn))

    with (
        patch.dict("os.environ", {"DATABASE_URL": "postgresql://example"}),
        patch("app.KPR_functions.psycopg2", fake_psycopg2),
        patch("app.KPR_functions._ensure_snapshot_schema", return_value=None),
    ):
        result = total_files_over_time()

    assert result == [
        {"captured_at": "2026-01-01T10:00:00Z", "total_files_registered": 12},
        {"captured_at": "2026-01-02T10:00:00Z", "total_files_registered": 18},
    ]
    assert "ORDER BY 1" in cursor.executed[0][0]
    fake_psycopg2.connect.assert_called_once_with(
        "postgresql://example",
        connect_timeout=5,
    )


def test_total_files_flagged_over_time_returns_rows_ordered_by_first_column():
    rows = [
        ("2026-01-01T10:00:00Z", 4),
        ("2026-01-02T10:00:00Z", 7),
    ]
    cursor = FakeCursor(rows)
    conn = FakeConnection(cursor)
    fake_psycopg2 = MagicMock(connect=MagicMock(return_value=conn))

    with (
        patch.dict("os.environ", {"DATABASE_URL": "postgresql://example"}),
        patch("app.KPR_functions.psycopg2", fake_psycopg2),
        patch("app.KPR_functions._ensure_snapshot_schema", return_value=None),
    ):
        result = total_files_flagged_over_time()

    assert result == [
        {"captured_at": "2026-01-01T10:00:00Z", "total_files_flagged": 4},
        {"captured_at": "2026-01-02T10:00:00Z", "total_files_flagged": 7},
    ]
    assert "total_files_flagged" in cursor.executed[0][0]
    assert "ORDER BY 1" in cursor.executed[0][0]
    fake_psycopg2.connect.assert_called_once_with(
        "postgresql://example",
        connect_timeout=5,
    )


def test_percentage_files_flagged_over_time_returns_rows_ordered_by_first_column():
    rows = [
        ("2026-01-01T10:00:00Z", 12.5),
        ("2026-01-02T10:00:00Z", 18.75),
    ]
    cursor = FakeCursor(rows)
    conn = FakeConnection(cursor)
    fake_psycopg2 = MagicMock(connect=MagicMock(return_value=conn))

    with (
        patch.dict("os.environ", {"DATABASE_URL": "postgresql://example"}),
        patch("app.KPR_functions.psycopg2", fake_psycopg2),
        patch("app.KPR_functions._ensure_snapshot_schema", return_value=None),
    ):
        result = percentage_files_flagged_over_time()

    assert result == [
        {"captured_at": "2026-01-01T10:00:00Z", "percentage_files_flagged": 12.5},
        {"captured_at": "2026-01-02T10:00:00Z", "percentage_files_flagged": 18.75},
    ]
    assert "percentage_files_flagged" in cursor.executed[0][0]
    assert "ORDER BY 1" in cursor.executed[0][0]
    fake_psycopg2.connect.assert_called_once_with(
        "postgresql://example",
        connect_timeout=5,
    )
