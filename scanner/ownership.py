"""Dual-owner attribution.

Every file resolves to a responsible person — never "nobody":
  * Direct owner      — personal stores (OneDrive): the file's data subject / submitter.
  * Master of Data    — shared stores (SharePoint, file shares): a designated steward.

Source type and steward are derived deterministically from the file name so repeated
scans attribute identically. The data-subject → user match uses names seeded in the DB.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from scanner import store

# filename keyword → (source_type, steward role for Master of Data)
_DOCTYPE_RULES = [
    ("expense",   "onedrive",   None),            # personal store, direct owner
    ("training",  "onedrive",   None),            # personal store, direct owner
    ("it_access", "sharepoint", "steward_it"),    # shared store, Master of Data
    ("supplier",  "sharepoint", "steward_proc"),  # shared store, Master of Data
    ("incident",  "fileshare",  "steward_comp"),  # shared store, Master of Data
]

DEFAULT_SOURCE = ("fileshare", "steward_comp")


def classify(path: str) -> tuple[str, Optional[str]]:
    """Return (source_type, steward_user_id_or_None) for a file path."""
    name = Path(path).name.lower()
    for key, source_type, steward in _DOCTYPE_RULES:
        if key in name:
            return source_type, steward
    return DEFAULT_SOURCE


def _match_subject(primary_name: Optional[str]) -> Optional[str]:
    """Find a seeded employee whose name matches the document's primary subject."""
    if not primary_name:
        return None
    target = primary_name.strip().lower()
    for u in store.list_users(role="employee"):
        if u["name"].lower() == target:
            return u["id"]
    return None


def resolve(path: str, primary_name: Optional[str]) -> tuple[str, Optional[str], Optional[str]]:
    """Return (source_type, owner_user_id, master_of_data_user_id).

    OneDrive → direct owner is the data subject (fallback: a default employee).
    SharePoint / file share → Master of Data is the steward; no personal direct owner.
    """
    source_type, steward = classify(path)

    if source_type == "onedrive":
        owner = _match_subject(primary_name)
        if owner is None:  # never leave a personal file unattributed
            employees = store.list_users(role="employee")
            owner = employees[0]["id"] if employees else None
        return source_type, owner, None

    # shared store: responsibility sits with the Master of Data steward
    master = steward
    if master and store.get_user(master) is None:
        master = None
    if master is None:
        employees = store.list_users(role="employee")
        master = employees[0]["id"] if employees else None
    return source_type, None, master
