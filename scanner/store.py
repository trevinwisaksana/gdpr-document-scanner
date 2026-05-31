"""SQLite persistence for the GDPR data-discovery tool.

Single shared DB file (path from GDPR_DB env or data/gdpr.db). State lives here so it
survives Streamlit reruns and tab backgrounding, and so repeated scans are reproducible.
All write paths use stable, content-derived IDs — re-scanning unchanged data is idempotent.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

DB_PATH = Path(os.getenv("GDPR_DB", Path(__file__).parent.parent / "data" / "gdpr.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('employee','admin'))
);

CREATE TABLE IF NOT EXISTS files (
    id                      TEXT PRIMARY KEY,
    path                    TEXT NOT NULL UNIQUE,
    source_type             TEXT NOT NULL CHECK (source_type IN ('onedrive','sharepoint','fileshare')),
    size_bytes              INTEGER NOT NULL,
    last_modified           REAL NOT NULL,
    owner_user_id           TEXT REFERENCES users(id),
    master_of_data_user_id  TEXT REFERENCES users(id),
    last_scanned_at         REAL
);

CREATE TABLE IF NOT EXISTS findings (
    id              TEXT PRIMARY KEY,
    file_id         TEXT NOT NULL REFERENCES files(id),
    category        TEXT NOT NULL,
    snippet         TEXT NOT NULL,
    confidence      REAL NOT NULL,
    detector        TEXT NOT NULL,
    gdpr_articles   TEXT NOT NULL,            -- JSON list
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','confirmed_required','marked_for_deletion')),
    created_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL CHECK (type IN ('full','delta')),
    started_at      REAL NOT NULL,
    finished_at     REAL,
    files_scanned   INTEGER NOT NULL DEFAULT 0,
    bytes_scanned   INTEGER NOT NULL DEFAULT 0,
    files_flagged   INTEGER NOT NULL DEFAULT 0,
    files_skipped   INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running','done','error')),
    progress_pct    REAL NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_findings_file   ON findings(file_id);
CREATE INDEX IF NOT EXISTS idx_files_owner     ON files(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_files_master    ON files(master_of_data_user_id);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def reset_db() -> None:
    """Drop everything — used by the demo reset button before re-seeding."""
    with connect() as conn:
        for t in ("findings", "scan_runs", "files", "users"):
            conn.execute(f"DROP TABLE IF EXISTS {t}")
    init_db()


def is_empty() -> bool:
    init_db()
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


# ── stable IDs ────────────────────────────────────────────────────────────────

def file_id(path: str) -> str:
    return hashlib.sha256(path.encode()).hexdigest()[:16]


def finding_id(file_id_: str, category: str, start: int) -> str:
    """Content-derived: same file + category + offset → same id across reruns."""
    return hashlib.sha256(f"{file_id_}:{category}:{start}".encode()).hexdigest()[:16]


# ── users ─────────────────────────────────────────────────────────────────────

def upsert_user(id: str, name: str, email: str, role: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO users(id,name,email,role) VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, email=excluded.email, role=excluded.role",
            (id, name, email, role),
        )


def get_user(id: str) -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE id=?", (id,)).fetchone()


def list_users(role: Optional[str] = None) -> list[sqlite3.Row]:
    with connect() as conn:
        if role:
            return conn.execute("SELECT * FROM users WHERE role=? ORDER BY name", (role,)).fetchall()
        return conn.execute("SELECT * FROM users ORDER BY role, name").fetchall()


# ── files ─────────────────────────────────────────────────────────────────────

def upsert_file(
    path: str, source_type: str, size_bytes: int, last_modified: float,
    owner_user_id: Optional[str], master_of_data_user_id: Optional[str],
) -> str:
    fid = file_id(path)
    with connect() as conn:
        conn.execute(
            "INSERT INTO files(id,path,source_type,size_bytes,last_modified,owner_user_id,master_of_data_user_id) "
            "VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET size_bytes=excluded.size_bytes, "
            "last_modified=excluded.last_modified, owner_user_id=excluded.owner_user_id, "
            "master_of_data_user_id=excluded.master_of_data_user_id",
            (fid, path, source_type, size_bytes, last_modified, owner_user_id, master_of_data_user_id),
        )
    return fid


def mark_scanned(file_id_: str, when: float) -> None:
    with connect() as conn:
        conn.execute("UPDATE files SET last_scanned_at=? WHERE id=?", (when, file_id_))


def get_file(file_id_: str) -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM files WHERE id=?", (file_id_,)).fetchone()


def list_files() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM files ORDER BY path").fetchall()


def files_for_user(user_id: str) -> list[sqlite3.Row]:
    """Files the user is responsible for — direct owner OR Master of Data — that have findings."""
    with connect() as conn:
        return conn.execute(
            "SELECT f.*, COUNT(fd.id) AS n_findings "
            "FROM files f JOIN findings fd ON fd.file_id = f.id "
            "WHERE f.owner_user_id=? OR f.master_of_data_user_id=? "
            "GROUP BY f.id ORDER BY f.last_modified ASC",
            (user_id, user_id),
        ).fetchall()


def flagged_files_for_user(user_id: str) -> list[sqlite3.Row]:
    """Like files_for_user but also includes a comma-separated list of distinct finding categories."""
    with connect() as conn:
        return conn.execute(
            "SELECT f.*, COUNT(fd.id) AS n_findings, "
            "GROUP_CONCAT(DISTINCT fd.category) AS categories "
            "FROM files f JOIN findings fd ON fd.file_id = f.id "
            "WHERE f.owner_user_id=? OR f.master_of_data_user_id=? "
            "GROUP BY f.id ORDER BY f.last_modified DESC",
            (user_id, user_id),
        ).fetchall()


# ── findings ──────────────────────────────────────────────────────────────────

def replace_findings(file_id_: str, findings: list[dict]) -> int:
    """Idempotent: delete this file's findings, re-insert. Status is preserved per stable id."""
    with connect() as conn:
        prior = {
            r["id"]: r["status"]
            for r in conn.execute("SELECT id,status FROM findings WHERE file_id=?", (file_id_,))
        }
        conn.execute("DELETE FROM findings WHERE file_id=?", (file_id_,))
        for f in findings:
            fid = finding_id(file_id_, f["category"], f["start"])
            conn.execute(
                "INSERT INTO findings(id,file_id,category,snippet,confidence,detector,gdpr_articles,status,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    fid, file_id_, f["category"], f["snippet"], f["confidence"], f["detector"],
                    json.dumps(f["gdpr_articles"]), prior.get(fid, "open"), f.get("created_at", time.time()),
                ),
            )
    return len(findings)


def findings_for_file(file_id_: str) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM findings WHERE file_id=? ORDER BY category, id", (file_id_,)
        ).fetchall()


def set_finding_status(finding_id_: str, status: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE findings SET status=? WHERE id=?", (status, finding_id_))


def category_breakdown() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT category, COUNT(*) AS n FROM findings GROUP BY category ORDER BY n DESC"
        ).fetchall()


def source_breakdown() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT f.source_type, COUNT(DISTINCT f.id) AS n_files, COUNT(fd.id) AS n_findings "
            "FROM files f LEFT JOIN findings fd ON fd.file_id=f.id "
            "GROUP BY f.source_type ORDER BY n_findings DESC"
        ).fetchall()


# ── scan runs ─────────────────────────────────────────────────────────────────

def create_scan_run(run_id: str, type_: str, started_at: float) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO scan_runs(id,type,started_at,status,progress_pct) VALUES(?,?,?, 'running', 0.0)",
            (run_id, type_, started_at),
        )


def update_scan_run(run_id: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with connect() as conn:
        conn.execute(f"UPDATE scan_runs SET {cols} WHERE id=?", (*fields.values(), run_id))


def latest_scan_run() -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM scan_runs ORDER BY started_at DESC LIMIT 1").fetchone()


def get_scan_run(run_id: str) -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM scan_runs WHERE id=?", (run_id,)).fetchone()


# ── dashboard aggregates ──────────────────────────────────────────────────────

def kpis() -> dict:
    with connect() as conn:
        files_scanned = conn.execute(
            "SELECT COUNT(*) FROM files WHERE last_scanned_at IS NOT NULL"
        ).fetchone()[0]
        files_flagged = conn.execute(
            "SELECT COUNT(DISTINCT file_id) FROM findings"
        ).fetchone()[0]
        bytes_scanned = conn.execute(
            "SELECT COALESCE(SUM(size_bytes),0) FROM files WHERE last_scanned_at IS NOT NULL"
        ).fetchone()[0]
        total_findings = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    last = latest_scan_run()
    duration = (last["finished_at"] - last["started_at"]) if last and last["finished_at"] else None
    return {
        "files_scanned": files_scanned,
        "files_flagged": files_flagged,
        "bytes_scanned": bytes_scanned,
        "total_findings": total_findings,
        "last_scan_type": last["type"] if last else None,
        "last_scan_duration": duration,
        "last_scan_progress": last["progress_pct"] if last else 0.0,
        "last_scan_skipped": last["files_skipped"] if last else 0,
    }
