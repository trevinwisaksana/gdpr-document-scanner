"""GDPR Data Discovery — Streamlit entrypoint.

Single-process app: a session-state router over three views (login / my files / admin).
State lives in SQLite (scanner.store) so it survives reruns and tab backgrounding, and so
repeated scans are reproducible. Seed data loads on first boot so the UI is alive instantly.
"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

from scanner import seed, store
from ui import admin, login, my_files, shell

st.set_page_config(page_title="GDPR Data Discovery", page_icon="🛡️", layout="wide")
shell.inject_css()

# Seed demo users + an initial scan on first boot (idempotent).
if store.is_empty():
    with st.spinner("Preparing demo data — scanning sample files…"):
        seed.seed()

st.session_state.setdefault("user_id", None)
st.session_state.setdefault("view", "login")


def _sidebar(user) -> None:
    initials = shell.avatar_initials(user["name"])
    color = shell.avatar_color(user["name"])
    with st.sidebar:
        st.markdown(
            '<div class="ae-side-brand">'
            '<div class="ae-side-mark">🛡</div>'
            '<div><div class="ae-side-brand-name">GDPR Discovery</div>'
            '<div class="ae-side-brand-sub">Data Discovery</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="ae-side-group">Workspace</div>', unsafe_allow_html=True)
        options = ["me", "admin"] if user["role"] == "admin" else ["me"]
        labels = {"me": "My files", "admin": "Admin dashboard"}
        view = st.radio(
            "View", options, format_func=lambda v: labels[v],
            index=options.index(st.session_state.view) if st.session_state.view in options else 0,
            label_visibility="collapsed",
        )
        st.session_state.view = view
        st.markdown('<div class="ae-side-group">Session</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;padding:8px 10px;margin-bottom:6px">'
            f'<div class="ae-avatar" style="background:{color};width:30px;height:30px;font-size:0.65rem">'
            f'{shell.esc(initials)}</div>'
            f'<div><div style="font-size:0.78rem;font-weight:600;color:var(--text);font-family:\'IBM Plex Sans\',sans-serif">'
            f'{shell.esc(user["name"])}</div>'
            f'<div style="font-size:0.66rem;color:var(--text-faint);font-family:\'IBM Plex Sans\',sans-serif">'
            f'{shell.esc(user["role"])}</div></div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Switch account", use_container_width=True):
            st.session_state.user_id = None
            st.session_state.view = "login"
            st.rerun()


user = store.get_user(st.session_state.user_id) if st.session_state.user_id else None

if user is None:
    login.render()
else:
    _sidebar(user)
    if st.session_state.view == "admin" and user["role"] == "admin":
        admin.render(user)
    else:
        my_files.render(user)

st.markdown(
    '<div class="ae-footer">Prototype — TECHon hackathon · Bosch GDPR challenge. '
    'Findings assist review; deletion is always a human decision.</div>',
    unsafe_allow_html=True,
)
