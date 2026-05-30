"""Mock login — pick a seeded user. No passwords; this is a prototype."""
from __future__ import annotations

import streamlit as st

from scanner import store
from ui import shell


def render() -> None:
    shell.navbar("Sign in")
    st.markdown(
        '<div style="max-width:460px;margin:6vh auto 0">'
        '<div class="mg-file-title" style="font-size:1.4rem;margin-bottom:4px">Who are you?</div>'
        '<div class="mg-file-meta" style="font-family:-apple-system,sans-serif;font-size:0.85rem;color:#6b6459">'
        'Pick an account to see the GDPR findings you are responsible for. '
        'Employees see only their own files; the DPO sees the admin dashboard.</div></div>',
        unsafe_allow_html=True,
    )

    users = store.list_users()
    if not users:
        st.warning("No users seeded yet. Run the admin reset or `python -m scanner.seed`.")
        return

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        labels = {u["id"]: f"{u['name']}  ·  {u['role']}" for u in users}
        choice = st.selectbox(
            "Account", list(labels.keys()), format_func=lambda i: labels[i],
            label_visibility="collapsed",
        )
        if st.button("Sign in", use_container_width=True, type="primary"):
            st.session_state.user_id = choice
            user = store.get_user(choice)
            st.session_state.view = "admin" if user["role"] == "admin" else "me"
            st.rerun()
