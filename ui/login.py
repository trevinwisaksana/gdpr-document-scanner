"""Login — pick a seeded user. Prototype; no passwords."""
from __future__ import annotations

import streamlit as st

from scanner import store
from ui import shell


def render() -> None:
    users = store.list_users()

    # center a narrow column
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        st.markdown(
            '<div class="ae-login-card" style="margin:8vh 0 0">'
            '<div class="ae-login-mark">🛡</div>'
            '<div class="ae-login-title">GDPR Data Discovery</div>'
            '<div class="ae-login-sub">Find and resolve personal data across your file '
            'sources. Choose an account — employees see only their own flagged files; '
            'the DPO sees the full estate.</div>'
            '<div class="ae-login-pick">Select account</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        if not users:
            st.warning("No users seeded. Run admin reset.")
            return

        for u in users:
            initials = shell.avatar_initials(u["name"])
            color    = shell.avatar_color(u["name"])
            role_cls = "admin" if u["role"] == "admin" else ""
            st.markdown(
                f'<div class="ae-acct" style="margin-bottom:7px">'
                f'<div class="ae-avatar" style="background:{color}">{shell.esc(initials)}</div>'
                f'<div style="flex:1;min-width:0">'
                f'<div class="ae-acct-name">{shell.esc(u["name"])}</div>'
                f'<div class="ae-acct-role">'
                f'<span class="ae-role-tag {role_cls}">{shell.esc(u["role"])}</span>'
                f'</div></div></div>',
                unsafe_allow_html=True,
            )
            if st.button(
                f"Sign in as {u['name']}",
                key=f"login_{u['id']}",
                use_container_width=True,
            ):
                st.session_state.user_id = u["id"]
                st.session_state.view = "admin" if u["role"] == "admin" else "me"
                st.rerun()

        st.markdown(
            '<div class="ae-login-foot">Prototype · TECHon hackathon · Bosch GDPR challenge</div>',
            unsafe_allow_html=True,
        )
