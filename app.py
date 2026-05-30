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
from ui import admin, login, me, shell

st.set_page_config(page_title="GDPR Data Discovery", page_icon="🛡️", layout="wide")
shell.inject_css()

# Seed demo users + an initial scan on first boot (idempotent).
if store.is_empty():
    with st.spinner("Preparing demo data — scanning sample files…"):
        seed.seed()

st.session_state.setdefault("user_id", None)
st.session_state.setdefault("view", "login")


def _sidebar(user) -> None:
    with st.sidebar:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:8px;padding:10px 0 4px">'
            '<span style="font-size:1rem">🛡️</span>'
            '<span style="font-size:0.95rem;font-weight:700;color:#1a1814;font-family:-apple-system,sans-serif">'
            'GDPR Discovery</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="mg-file-meta" style="margin:4px 0 8px">Signed in as<br>'
            f'<strong style="color:#1a1814;font-family:-apple-system,sans-serif">{shell.esc(user["name"])}</strong> '
            f'· {shell.esc(user["role"])}</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="mg-section">VIEW</div>', unsafe_allow_html=True)
        options = ["me", "admin"] if user["role"] == "admin" else ["me"]
        labels = {"me": "My files", "admin": "Admin dashboard"}
        view = st.radio(
            "View", options, format_func=lambda v: labels[v],
            index=options.index(st.session_state.view) if st.session_state.view in options else 0,
            label_visibility="collapsed",
        )
        st.session_state.view = view
        st.markdown('<div class="mg-section">SESSION</div>', unsafe_allow_html=True)
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
        me.render(user)

st.markdown(
    '<div class="mg-footer">Prototype — TECHon hackathon · Bosch GDPR challenge. '
    'Findings assist review; deletion is always a human decision.</div>',
    unsafe_allow_html=True,
)
