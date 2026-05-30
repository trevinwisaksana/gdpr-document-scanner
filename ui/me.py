"""Employee view (Priority 2): the flagged files this user is responsible for, the
findings inside each, and the two guided actions. Nothing deletes automatically — the
user always has the last word."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from scanner import gdpr, scan, store
from ui import shell

_ACTION_LABEL = {
    "open": "",
    "confirmed_required": "✓ Confirmed required for business",
    "marked_for_deletion": "🗑 Marked for deletion",
}


def render(user) -> None:
    shell.navbar(
        "My files",
        right=f'<span style="color:#6b6459">{shell.esc(user["name"])}</span>',
    )

    files = store.files_for_user(user["id"])
    n_findings = sum(f["n_findings"] for f in files)
    overdue = sum(1 for f in files if scan.is_past_retention(f["last_modified"]))
    shell.stat_cards([
        (str(len(files)), "Flagged files", True),
        (str(n_findings), "Findings", False),
        (str(overdue), "Past retention (3y)", False),
    ])

    if not files:
        st.success("You have no flagged files. Nothing to review.")
        return

    st.markdown(
        '<div class="mg-file-meta" style="font-family:-apple-system,sans-serif;color:#6b6459;'
        'font-size:0.8rem;margin:4px 0 14px">You are attributed these files as the direct owner '
        'or Master of Data. Review each finding and either confirm it is required, or mark the '
        'file for cleanup. <strong>The tool never deletes anything for you.</strong></div>',
        unsafe_allow_html=True,
    )

    for f in files:
        _file_block(f, user)


def _file_block(f, user) -> None:
    name = Path(f["path"]).name
    past = scan.is_past_retention(f["last_modified"])
    badge = ('<span class="mg-badge-retention">OLDER THAN 3 YEARS</span>'
             if past else '<span class="mg-badge-ok">within retention</span>')
    label = f"{name}   —   {f['n_findings']} finding(s)"

    with st.expander(label, expanded=False):
        owner = store.get_user(f["owner_user_id"]) if f["owner_user_id"] else None
        master = store.get_user(f["master_of_data_user_id"]) if f["master_of_data_user_id"] else None
        responsible = (f'Direct owner: {owner["name"]}' if owner
                       else f'Master of Data: {master["name"]}' if master else "Unattributed")
        st.markdown(
            f'<div style="margin-bottom:10px">'
            f'<span class="mg-badge-src">{shell.esc(f["source_type"])}</span> '
            f'{badge} '
            f'<span class="mg-file-meta">· {responsible} · '
            f'{shell.human_bytes(f["size_bytes"])}</span></div>',
            unsafe_allow_html=True,
        )

        for fd in store.findings_for_file(f["id"]):
            _finding_card(fd)


def _finding_card(fd) -> None:
    import json
    color = shell.CATEGORY_COLOR.get(fd["category"], "#0c8275")
    arts = json.loads(fd["gdpr_articles"])
    arts_html = "".join(f'<span class="mg-pill art">{a}</span>' for a in arts)
    status_html = ""
    if fd["status"] == "confirmed_required":
        status_html = '<span class="mg-status-confirmed">✓ REQUIRED FOR BUSINESS</span>'
    elif fd["status"] == "marked_for_deletion":
        status_html = '<span class="mg-status-delete">🗑 MARKED FOR DELETION</span>'

    st.markdown(
        f'<div class="mg-finding" style="border-left-color:{color}">'
        f'<div class="mg-finding-hdr">'
        f'<span style="font-size:1rem">{gdpr.icon(fd["category"])}</span>'
        f'<span class="mg-finding-cat">{shell.esc(gdpr.label(fd["category"]))}</span>'
        f'<span class="mg-pill conf">{fd["confidence"]*100:.0f}%</span>'
        f'<span class="mg-pill det">{shell.esc(fd["detector"])}</span>'
        f'<span style="flex:1"></span>{status_html}</div>'
        f'<span class="mg-snippet">{shell.esc(fd["snippet"])}</span>'
        f'<div class="mg-why">{arts_html} &nbsp; {shell.esc(gdpr.WHY.get(fd["category"], ""))}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    c1, c2, _ = st.columns([1.2, 1.2, 3])
    with c1:
        if st.button("Required for business", key=f"req_{fd['id']}"):
            store.set_finding_status(fd["id"], "confirmed_required")
            st.rerun()
    with c2:
        if st.button("Mark for deletion", key=f"del_{fd['id']}"):
            store.set_finding_status(fd["id"], "marked_for_deletion")
            st.rerun()
