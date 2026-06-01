"""KPI helpers for the GCP Postgres database."""
from __future__ import annotations

import json
import os
import threading
from typing import Any

try:
    import psycopg2
    import psycopg2.pool as psycopg2_pool
except ModuleNotFoundError:  # pragma: no cover - exercised only when psycopg2 is absent
    psycopg2 = None
    psycopg2_pool = None


_POOL_LOCK = threading.Lock()
_POOL: Any | None = None
_SNAPSHOT_SCHEMA_LOCK = threading.Lock()
_SNAPSHOT_SCHEMA_READY = False

_SNAPSHOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id                          BIGSERIAL PRIMARY KEY,
    captured_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    run_label                   TEXT,
    total_files_registered      INTEGER NOT NULL,
    total_files_flagged         INTEGER NOT NULL,
    total_files_processed       INTEGER NOT NULL,
    percentage_files_flagged    NUMERIC(7,2) NOT NULL,
    owners                      JSONB NOT NULL DEFAULT '[]'::jsonb,
    flagged_files_per_owner     JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_kpi_snapshots_captured_at
    ON kpi_snapshots (captured_at DESC);
"""


def _get_pool() -> Any:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    if psycopg2_pool is None:
        raise RuntimeError("psycopg2 is not installed")

    global _POOL
    if _POOL is None:
        max_messages = int(os.getenv("MAX_MESSAGES", "10"))
        with _POOL_LOCK:
            if _POOL is None:
                _POOL = psycopg2_pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=max_messages + 2,
                    dsn=database_url,
                )
    return _POOL


def _fetch_scalar(query: str, params: tuple[Any, ...] = ()) -> int:
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
        conn.commit()
        return int(row[0]) if row else 0
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def total_files_registered() -> int:
    """Return the total number of files registered in the GCP Postgres DB."""
    return _fetch_scalar("SELECT COUNT(*) FROM drive_files")


def total_files_flagged() -> int:
    """Return the total number of files flagged by the scanner."""
    return _fetch_scalar(
        "SELECT COUNT(*) FROM drive_files WHERE status_flag = %s",
        ("flagged",),
    )


def total_files_processed() -> int:
    """Return the total number of files that are not still marked not checked."""
    return _fetch_scalar(
        "SELECT COUNT(*) FROM drive_files WHERE status_flag IS DISTINCT FROM %s",
        ("not checked",),
    )


def percentage_files_flagged() -> float:
    """Return the percentage of processed files that were flagged."""
    processed = total_files_processed()
    if processed == 0:
        return 0.0
    return total_files_flagged() / processed * 100.0


def list_all_owners() -> list[str]:
    """Return all distinct file owners recorded in drive_files."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT owner
                FROM drive_files
                WHERE owner IS NOT NULL AND owner <> %s
                ORDER BY owner
                """,
                ("",),
            )
            rows = cur.fetchall()
        conn.commit()
        return [str(row[0]) for row in rows if row and row[0] is not None]
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def flagged_files_per_owner() -> list[dict[str, Any]]:
    """Return flagged-file counts grouped by owner."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT owner, COUNT(*)::int AS flagged_files
                FROM drive_files
                WHERE status_flag = %s AND owner IS NOT NULL AND owner <> %s
                GROUP BY owner
                ORDER BY flagged_files DESC, owner
                """,
                ("flagged", ""),
            )
            rows = cur.fetchall()
        conn.commit()
        return [
            {"owner": str(row[0]), "flagged_files": int(row[1])}
            for row in rows
            if row and row[0] is not None
        ]
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def _ensure_snapshot_schema(conn) -> None:
    global _SNAPSHOT_SCHEMA_READY
    if _SNAPSHOT_SCHEMA_READY:
        return
    with _SNAPSHOT_SCHEMA_LOCK:
        if _SNAPSHOT_SCHEMA_READY:
            return
        with conn.cursor() as cur:
            cur.execute(_SNAPSHOT_SCHEMA)
        conn.commit()
        _SNAPSHOT_SCHEMA_READY = True


def _coerce_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def record_kpi_snapshot(run_label: str | None = None) -> dict[str, Any]:
    """Store a point-in-time KPI snapshot in the live Postgres DB."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is not installed")

    label = run_label or "manual"
    with psycopg2.connect(database_url, connect_timeout=5) as conn:
        _ensure_snapshot_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)::int AS total_files_registered,
                    COUNT(*) FILTER (WHERE status_flag = %s)::int AS total_files_flagged,
                    COUNT(*) FILTER (WHERE status_flag IS DISTINCT FROM %s)::int AS total_files_processed
                FROM drive_files
                """,
                ("flagged", "not checked"),
            )
            totals = cur.fetchone() or (0, 0, 0)
            total_files_registered = int(totals[0])
            total_files_flagged = int(totals[1])
            total_files_processed = int(totals[2])
            percentage_files_flagged = (
                (total_files_flagged / total_files_processed) * 100.0
                if total_files_processed
                else 0.0
            )

            cur.execute(
                """
                SELECT COALESCE(json_agg(owner ORDER BY owner), '[]'::json)
                FROM (
                    SELECT DISTINCT owner
                    FROM drive_files
                    WHERE owner IS NOT NULL AND owner <> %s
                    ORDER BY owner
                ) owners
                """,
                ("",),
            )
            owners = _coerce_json(cur.fetchone()[0] or [])

            cur.execute(
                """
                SELECT COALESCE(
                    json_agg(
                        json_build_object('owner', owner, 'flagged_files', flagged_files)
                        ORDER BY flagged_files DESC, owner
                    ),
                    '[]'::json
                )
                FROM (
                    SELECT owner, COUNT(*)::int AS flagged_files
                    FROM drive_files
                    WHERE status_flag = %s AND owner IS NOT NULL AND owner <> %s
                    GROUP BY owner
                ) by_owner
                """,
                ("flagged", ""),
            )
            flagged_files_by_owner = _coerce_json(cur.fetchone()[0] or [])

            cur.execute(
                """
                INSERT INTO kpi_snapshots (
                    run_label,
                    total_files_registered,
                    total_files_flagged,
                    total_files_processed,
                    percentage_files_flagged,
                    owners,
                    flagged_files_per_owner
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                RETURNING id, captured_at
                """,
                (
                    label,
                    total_files_registered,
                    total_files_flagged,
                    total_files_processed,
                    percentage_files_flagged,
                    json.dumps(owners),
                    json.dumps(flagged_files_by_owner),
                ),
            )
            snapshot_id, captured_at = cur.fetchone()
        conn.commit()

    return {
        "id": int(snapshot_id),
        "captured_at": captured_at,
        "run_label": label,
        "total_files_registered": total_files_registered,
        "total_files_flagged": total_files_flagged,
        "total_files_processed": total_files_processed,
        "percentage_files_flagged": percentage_files_flagged,
        "owners": owners,
        "flagged_files_per_owner": flagged_files_by_owner,
    }


def list_kpi_snapshots(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent KPI snapshots, newest first."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is not installed")

    with psycopg2.connect(database_url, connect_timeout=5) as conn:
        _ensure_snapshot_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, captured_at, run_label,
                    total_files_registered, total_files_flagged,
                    total_files_processed, percentage_files_flagged,
                    owners, flagged_files_per_owner
                FROM kpi_snapshots
                ORDER BY captured_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "id": int(row[0]),
            "captured_at": row[1],
            "run_label": row[2],
            "total_files_registered": int(row[3]),
            "total_files_flagged": int(row[4]),
            "total_files_processed": int(row[5]),
            "percentage_files_flagged": float(row[6]),
            "owners": _coerce_json(row[7]),
            "flagged_files_per_owner": _coerce_json(row[8]),
        }
        for row in rows
    ]


def total_files_over_time() -> list[dict[str, Any]]:
    """Return the registered-file trend over time, oldest first."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is not installed")

    with psycopg2.connect(database_url, connect_timeout=5) as conn:
        _ensure_snapshot_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT captured_at, total_files_registered
                FROM kpi_snapshots
                ORDER BY 1
                """
            )
            rows = cur.fetchall()

    return [
        {
            "captured_at": row[0],
            "total_files_registered": int(row[1]),
        }
        for row in rows
    ]


def total_files_flagged_over_time() -> list[dict[str, Any]]:
    """Return the flagged-file trend over time, oldest first."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is not installed")

    with psycopg2.connect(database_url, connect_timeout=5) as conn:
        _ensure_snapshot_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT captured_at, total_files_flagged
                FROM kpi_snapshots
                ORDER BY 1
                """
            )
            rows = cur.fetchall()

    return [
        {
            "captured_at": row[0],
            "total_files_flagged": int(row[1]),
        }
        for row in rows
    ]


def percentage_files_flagged_over_time() -> list[dict[str, Any]]:
    """Return the flagged-percentage trend over time, oldest first."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is not installed")

    with psycopg2.connect(database_url, connect_timeout=5) as conn:
        _ensure_snapshot_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT captured_at, percentage_files_flagged
                FROM kpi_snapshots
                ORDER BY 1
                """
            )
            rows = cur.fetchall()

    return [
        {
            "captured_at": row[0],
            "percentage_files_flagged": float(row[1]),
        }
        for row in rows
    ]
