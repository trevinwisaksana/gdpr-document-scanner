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
    # steward_comp = gets fileshare files via ownership rules + alphabetically first employee
    ("steward_comp", "Amara Okafor",  "amara.okafor@bosch.example",  "employee"),
    # plain employee — no files attributed, shows empty state
    ("emp_clean",    "Tom Richter",   "tom.richter@bosch.example",   "employee"),
    ("admin_dpo",    "Klaus Weber",   "klaus.weber@bosch.example",   "admin"),
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
