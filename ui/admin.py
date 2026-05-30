"""Admin dashboard (Priority 3): KPIs, live scan controls, and finding breakdowns."""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from scanner import escalate, scan, seed, store
from ui import shell


def render(user) -> None:
    engine = "OpenRouter on" if escalate.is_enabled() else "deterministic"
    shell.navbar("Admin dashboard", right=f'<span style="color:#6b6459">{engine}</span>')

    _kpis()
    _controls()
    _breakdowns()


def _kpis() -> None:
    k = store.kpis()
    dur = f"{k['last_scan_duration']:.1f}s" if k["last_scan_duration"] else "—"
    shell.stat_cards([
        (str(k["files_scanned"]), "Files scanned", True),
        (str(k["files_flagged"]), "Files flagged", False),
        (shell.human_bytes(k["bytes_scanned"]), "Volume scanned", False),
        (dur, f"Last scan ({k['last_scan_type'] or '—'})", False),
        (str(k["total_findings"]), "Total findings", False),
    ])


def _controls() -> None:
    st.markdown('<div class="mg-section">SCAN CONTROL</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    run_full = c1.button("▶ Run Full Scan", use_container_width=True)
    run_delta = c2.button("⏩ Run Delta Scan", use_container_width=True)
    reset = c3.button("↻ Reset demo", use_container_width=True)

    if run_full:
        _run("full")
    elif run_delta:
        _run("delta")
    elif reset:
        with st.spinner("Re-seeding to a clean demo state…"):
            seed.seed(force=True)
        st.success("Demo reset.")
        st.rerun()


def _run(scan_type: str) -> None:
    bar = st.progress(0.0)
    beam = st.empty()
    beam.markdown('<div class="mg-scan"><div class="mg-scan-beam"></div></div>', unsafe_allow_html=True)
    status = st.empty()

    def cb(frac: float, label: str) -> None:
        bar.progress(min(frac, 1.0))
        status.markdown(
            f'<div class="mg-file-meta">scanning {shell.esc(label)} … {frac*100:.0f}%</div>',
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
        st.markdown('<div class="mg-section">FINDINGS BY CATEGORY</div>', unsafe_allow_html=True)
        from scanner import gdpr
        rows = [
            {"Category": gdpr.label(r["category"]), "Count": r["n"]}
            for r in store.category_breakdown()
        ]
        if rows:
            df = pd.DataFrame(rows).set_index("Category")
            st.bar_chart(df, color="#0c8275")
        else:
            st.caption("No findings yet — run a scan.")
    with col2:
        st.markdown('<div class="mg-section">BY SOURCE</div>', unsafe_allow_html=True)
        rows = [
            {"Source": r["source_type"], "Files": r["n_files"], "Findings": r["n_findings"]}
            for r in store.source_breakdown()
        ]
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.caption("No data yet.")
