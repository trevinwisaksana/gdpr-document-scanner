"""Seed demo users and run an initial scan so the UI is populated on first boot.

Idempotent: safe to call on every startup. Pass force=True (or run as a module) to
reset to a clean, known demo state — used by the admin 'Reset demo' button.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from scanner import scan, store

# Stewards' ids are referenced by ownership._DOCTYPE_RULES — keep in sync.
USERS = [
    ("steward_it",   "Jonas Keller",    "jonas.keller@bosch.example",    "employee"),
    ("steward_proc", "Maria Lang",      "maria.lang@bosch.example",      "employee"),
    ("steward_comp", "Thomas Richter",  "thomas.richter@bosch.example",  "employee"),
    ("emp_sara",     "Sara Hoffmann",   "sara.hoffmann@bosch.example",   "employee"),
    ("emp_elena",    "Elena Fischer",   "elena.fischer@bosch.example",   "employee"),
    ("emp_nina",     "Nina Beck",       "nina.beck@bosch.example",       "employee"),
    ("emp_philipp",  "Philipp Neumann", "philipp.neumann@bosch.example", "employee"),
    ("admin_dpo",    "Klaus Weber (DPO)", "klaus.weber@bosch.example",   "admin"),
]


# Backdate a couple of sample files on disk so the 3-year retention rule has
# deletion candidates to show. mtime persists across re-scans.
_BACKDATE = ["Expense_Report_Example_A.pdf", "IT_Access_Request_Example_B.pdf"]


def seed_users() -> None:
    for uid, name, email, role in USERS:
        store.upsert_user(uid, name, email, role)


def backdate_samples(years: int = 4) -> None:
    old = time.time() - years * 365 * 86400
    root = Path(scan.SCAN_TARGET_DIR)
    for name in _BACKDATE:
        p = root / name
        if p.exists():
            os.utime(p, (old, old))


def seed(force: bool = False) -> None:
    if force:
        store.reset_db()
    if not store.is_empty():
        return
    store.init_db()
    seed_users()
    backdate_samples()
    # initial full scan so /me and /admin are alive immediately
    scan.run_scan(scan_type="full")


if __name__ == "__main__":
    seed(force=True)
    k = store.kpis()
    print(f"Seeded. files_scanned={k['files_scanned']} files_flagged={k['files_flagged']} "
          f"findings={k['total_findings']}")
