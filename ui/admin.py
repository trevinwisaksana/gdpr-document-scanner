"""Admin dashboard: KPIs, live scan controls, and finding breakdowns."""
from __future__ import annotations

import time

import pandas as pd
import requests
import streamlit as st

from scanner import escalate, gdpr, scan, seed, store
from ui import shell

CLOUD_SCAN_URL = "https://gdpr-document-scanner-lotcfrcujq-uc.a.run.app/workflows/drive/scan"


def render(user) -> None:
    engine = "OpenRouter on" if escalate.is_enabled() else "engine: deterministic"
    shell.navbar("Admin dashboard", right=engine)

    _kpis()
    _scan_control()
    _breakdowns()


def _kpis() -> None:
    k = store.kpis()
    dur = f"{k['last_scan_duration']:.1f}s" if k["last_scan_duration"] else "—"
    pct = (
        f"{k['files_flagged'] / k['files_scanned'] * 100:.1f}% of scanned"
        if k["files_scanned"] else ""
    )
    shell.kpi_grid([
        {"num": str(k["files_scanned"]),  "label": "Files scanned",   "variant": "accent", "meta": "across all sources"},
        {"num": str(k["files_flagged"]),  "label": "Files flagged",   "variant": "flag",   "meta": pct},
        {"num": str(k["total_findings"]), "label": "Total findings",  "variant": "flag"},
        {"num": shell.human_bytes(k["bytes_scanned"]), "label": "Volume scanned", "meta": ""},
        {"num": dur, "label": f"Last scan", "meta": k["last_scan_type"] or "—"},
    ])


def _scan_control() -> None:
    shell.section_label("Scan control")

    st.markdown(
        '<div class="ae-scan-panel">'
        '<div class="ae-scan-info">'
        '<div class="ae-scan-title">Ready to scan</div>'
        '<div class="ae-scan-sub">Run against sample files locally, or trigger the live '
        'Google Drive scan on GCP.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1.2])
    run_gdrive = c1.button("☁️  Scan Google Drive", use_container_width=True, type="primary")
    run_full   = c2.button("▶  Full scan",          use_container_width=True)
    run_delta  = c3.button("⏩  Delta scan",          use_container_width=True)
    reset      = c4.button("↻  Reset demo",          use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if run_gdrive:
        with st.spinner("Triggering Google Drive scan on GCP…"):
            try:
                r = requests.post(CLOUD_SCAN_URL, timeout=15)
                data = r.json()
                st.success("GCP scan triggered — running in background. Results will appear shortly.")
            except Exception as e:
                st.error(f"Failed to reach GCP endpoint: {e}")

    if run_full:
        _run("full")
    elif run_delta:
        _run("delta")
    elif reset:
        with st.spinner("Re-seeding demo…"):
            seed.seed(force=True)
        st.success("Demo reset.")
        st.rerun()


def _run(scan_type: str) -> None:
    bar = st.progress(0.0)
    beam = st.empty()
    beam.markdown(
        '<div class="ae-scan-beam-wrap"><div class="ae-scan-beam"></div></div>',
        unsafe_allow_html=True,
    )
    status = st.empty()

    def cb(frac: float, label: str) -> None:
        bar.progress(min(frac, 1.0))
        status.markdown(
            f'<div class="ae-kpi-meta">scanning {shell.esc(label)} … {frac*100:.0f}%</div>',
            unsafe_allow_html=True,
        )

    t0 = time.time()
    result = scan.run_scan(scan_type, progress_cb=cb)
    bar.progress(1.0)
    beam.empty()
    status.empty()
    st.success(
        f"{scan_type.title()} scan done in {result['duration']:.1f}s — "
        f"scanned {result['files_scanned']}, flagged {result['files_flagged']}, "
        f"skipped {result['files_skipped']}."
    )
    time.sleep(0.3)
    st.rerun()


def _breakdowns() -> None:
    col1, col2 = st.columns(2)

    with col1:
        shell.section_label("Findings by PII type")
        rows = store.category_breakdown()
        if rows:
            max_n = max(r["n"] for r in rows) or 1
            _pri_color = {"high": "#dc2626", "medium": "#d97706", "low": "#7e92a8"}
            html = ""
            for r in rows:
                w = int(r["n"] / max_n * 100)
                bar_color = _pri_color[gdpr.priority(r["category"])]
                html += (
                    f'<div class="ae-hbar-row">'
                    f'<div class="ae-hbar-label">{shell.esc(gdpr.label(r["category"]))}</div>'
                    f'<div class="ae-hbar-track"><div class="ae-hbar-fill" style="width:{w}%;background:{bar_color}"></div></div>'
                    f'<div class="ae-hbar-val">{r["n"]}</div>'
                    f'</div>'
                )
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.caption("No findings yet — run a scan.")

    with col2:
        shell.section_label("By source")
        rows = store.source_breakdown()
        if rows:
            max_files = max(r["n_files"] for r in rows) or 1
            for r in rows:
                w = int(r["n_files"] / max_files * 100)
                st.markdown(
                    f'<div class="ae-src-card">'
                    f'<div class="ae-src-top">'
                    f'<span class="ae-src-name">{shell.esc(r["source_type"])}</span>'
                    f'<span class="ae-src-stat">{r["n_files"]} files · {r["n_findings"]} findings</span>'
                    f'</div>'
                    f'<div class="ae-src-track"><div class="ae-src-fill" style="width:{w}%"></div></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No data yet.")
