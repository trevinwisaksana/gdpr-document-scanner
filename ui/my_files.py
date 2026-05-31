"""Employee view: flagged files this user is responsible for."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import requests
import streamlit as st

from scanner import gdpr, scan, store
from ui import shell

_API_BASE = os.getenv("API_BASE_URL", "https://gdpr-document-scanner-lotcfrcujq-uc.a.run.app")
logger = logging.getLogger(__name__)


def _fetch_flagged_files(user_id: str) -> list[dict]:
    """Fetch flagged files from the REST API; fall back to direct store access on failure."""
    try:
        resp = requests.get(f"{_API_BASE}/users/{user_id}/files", timeout=10)
        resp.raise_for_status()
        return resp.json()["files"]
    except Exception as exc:
        logger.warning("API unavailable (%s), falling back to store", exc)
        return [dict(row) for row in store.files_for_user(user_id)]


_PRI_ORDER  = {"high": 0, "medium": 1, "low": 2}
_PRI_EMOJI  = {"high": "🔴", "medium": "🟡", "low": "⚪"}
_PRI_COLORS = {"high": "#dc2626", "medium": "#d97706", "low": "#7e92a8"}
_PRI_BG     = {"high": "#fef2f2", "medium": "#fffbeb", "low": "#f4f7fb"}
_PRI_TEXT   = {"high": "#b91c1c", "medium": "#b45309", "low": "#7e92a8"}
_PRI_BORDER = {"high": "#fca5a5", "medium": "#fde68a", "low": "#dde3ec"}
_PRI_LABEL  = {"high": "HIGH RISK", "medium": "MEDIUM RISK", "low": "LOW RISK"}


def _file_max_priority(file_id: str) -> str:
    findings = store.findings_for_file(file_id)
    open_cats = [fd["category"] for fd in findings if fd["status"] == "open"]
    if not open_cats:
        return "low"
    pris = [gdpr.priority(c) for c in open_cats]
    if "high" in pris:
        return "high"
    if "medium" in pris:
        return "medium"
    return "low"


def render(user) -> None:
    shell.navbar("My files", right=shell.esc(user["name"]))

    files = _fetch_flagged_files(user["id"])
    files_with_pri = [(f, _file_max_priority(f["id"])) for f in files]
    files_with_pri.sort(key=lambda x: (_PRI_ORDER[x[1]], -x[0]["n_findings"]))

    reviewed = sum(
        1 for f in files
        if all(
            fd["status"] in ("confirmed_required", "marked_for_deletion")
            for fd in store.findings_for_file(f["id"])
        )
    ) if files else 0
    left = len(files) - reviewed
    pct = int(reviewed / len(files) * 100) if files else 100

    st.markdown(
        f'<div class="ae-strip">'
        f'<div class="ae-strip-item"><span class="ae-strip-num flag">{len(files)}</span>'
        f'<span class="ae-strip-lbl">flagged</span></div>'
        f'<span class="ae-strip-sep">|</span>'
        f'<div class="ae-strip-item"><span class="ae-strip-num ok">{reviewed}</span>'
        f'<span class="ae-strip-lbl">reviewed</span></div>'
        f'<span class="ae-strip-sep">|</span>'
        f'<div class="ae-strip-item"><span class="ae-strip-num">{left}</span>'
        f'<span class="ae-strip-lbl">left to review</span></div>'
        f'<div class="ae-strip-prog"><div class="ae-strip-prog-track">'
        f'<div class="ae-strip-prog-fill" style="width:{pct}%"></div></div>'
        f'<span class="ae-strip-prog-pct">{pct}%</span></div></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="ae-page-title">Files that may contain personal data</div>'
        '<div class="ae-page-sub">These files were flagged automatically by the scanner. '
        'You decide what happens to each one — nothing is deleted without your action.</div>',
        unsafe_allow_html=True,
    )

    if not files:
        st.success("No flagged files. Nothing to review.")
        return

    for f, pri in files_with_pri:
        _file_block(f, user, pri, f.get("finding_categories", []))


def _category_chips_html(categories: list[str]) -> str:
    chips = []
    for cat in categories:
        color = shell.CATEGORY_COLOR.get(cat, "#7e92a8")
        chips.append(
            f'<span style="background:{color}1a;color:{color};border:1px solid {color}55;'
            f'padding:2px 8px;border-radius:5px;font-size:0.65rem;font-weight:600;'
            f'font-family:IBM Plex Mono,monospace;white-space:nowrap">'
            f'{shell.esc(cat)}</span>'
        )
    return '<div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px">' + "".join(chips) + "</div>"


def _file_block(f, user, pri: str = "low", finding_categories: list[str] | None = None) -> None:
    name = Path(f["path"]).name
    past = scan.is_past_retention(f["last_modified"])
    findings = store.findings_for_file(f["id"])
    n_open = sum(1 for fd in findings if fd["status"] == "open")

    pri_bg     = _PRI_BG[pri]
    pri_txt    = _PRI_TEXT[pri]
    pri_border = _PRI_BORDER[pri]
    pri_color  = _PRI_COLORS[pri]

    retention_html = (
        '<span style="color:#b45309;font-size:0.72rem">⏰ Past 3-year retention</span>'
        if past else ""
    )
    review_html = (
        '<span style="margin-left:auto;font-size:0.72rem;color:#7e92a8">'
        + str(n_open) + " finding(s) to review</span>"
    )
    pill_html = (
        '<span style="background:' + pri_bg + ';color:' + pri_txt
        + ';border:1px solid ' + pri_border
        + ';padding:2px 9px;border-radius:5px;font-size:0.65rem;font-weight:700;'
        'letter-spacing:0.06em;font-family:monospace">' + _PRI_LABEL[pri] + '</span>'
    )

    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;margin-top:8px">'
        + pill_html + retention_html + review_html + '</div>',
        unsafe_allow_html=True,
    )

    label = _PRI_EMOJI[pri] + "  " + name
    with st.expander(label, expanded=False):
        size = shell.human_bytes(f["size_bytes"])
        modified = str(f["last_modified"])[:10] if f["last_modified"] else "—"
        path_str = f["path"] or ""

        st.markdown(
            '<div style="border-left:3px solid ' + pri_color + ';padding:8px 12px;'
            'background:' + pri_bg + ';border-radius:0 6px 6px 0;margin-bottom:12px;'
            'font-size:0.75rem;color:#4f6480;font-family:monospace">'
            + shell.esc(path_str)
            + '<span style="float:right">' + shell.esc(size)
            + " · modified " + shell.esc(modified) + "</span></div>",
            unsafe_allow_html=True,
        )

        if finding_categories:
            st.markdown(_category_chips_html(finding_categories), unsafe_allow_html=True)

        shell.section_label("Findings")
        for fd in findings:
            _finding_card(fd)


def _finding_card(fd) -> None:
    color = shell.CATEGORY_COLOR.get(fd["category"], "#2f7d8c")
    arts = json.loads(fd["gdpr_articles"])
    arts_html = "".join(
        '<span class="ae-article">' + a + "</span>" for a in arts
    )

    conf = fd["confidence"]
    conf_pct = int(conf * 100)
    conf_cls = "likely" if conf >= 0.8 else "possible" if conf >= 0.5 else "low"

    pri = gdpr.priority(fd["category"])
    pri_html = (
        '<span style="background:' + _PRI_BG[pri] + ';color:' + _PRI_TEXT[pri]
        + ';border:1px solid ' + _PRI_BORDER[pri]
        + ';padding:2px 8px;border-radius:5px;font-size:0.65rem;font-weight:700;'
        'letter-spacing:0.06em;font-family:monospace">' + _PRI_LABEL[pri] + '</span>'
    )

    status_html = ""
    if fd["status"] == "confirmed_required":
        status_html = '<span class="ae-status-confirmed">✓ Required for business</span>'
    elif fd["status"] == "marked_for_deletion":
        status_html = '<span class="ae-status-delete">🗑 Marked for deletion</span>'

    st.markdown(
        '<div class="ae-finding" style="border-left:3px solid ' + color + '">'
        '<div class="ae-finding-hdr">'
        '<span style="font-size:1rem">' + gdpr.icon(fd["category"]) + "</span>"
        '<span class="ae-finding-type">' + shell.esc(gdpr.label(fd["category"])) + "</span>"
        + pri_html
        + '<div class="ae-conf ' + conf_cls + '">'
        '<div class="ae-conf-bar"><i style="width:' + str(conf_pct) + '%"></i></div>'
        + str(conf_pct) + '%</div>'
        '<span class="ae-badge ae-badge-src">' + shell.esc(fd["detector"]) + "</span>"
        '<span style="flex:1"></span>' + status_html + "</div>"
        '<code class="ae-snippet">' + shell.esc(fd["snippet"]) + "</code>"
        '<div class="ae-why">' + arts_html + " "
        + shell.esc(gdpr.WHY.get(fd["category"], "")) + "</div></div>",
        unsafe_allow_html=True,
    )

    c1, c2, _ = st.columns([1.2, 1.4, 3])
    with c1:
        if st.button("Needed for business", key="req_" + fd["id"]):
            store.set_finding_status(fd["id"], "confirmed_required")
            st.rerun()
    with c2:
        if st.button("Mark for deletion", key="del_" + fd["id"]):
            store.set_finding_status(fd["id"], "marked_for_deletion")
            st.rerun()
