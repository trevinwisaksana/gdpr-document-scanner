"""Shared visual shell — skeuomorphic teal/cream CSS lifted from the original MosaicGuard
app, plus small render helpers reused across the login / me / admin views."""
from __future__ import annotations

import html as _html

import streamlit as st

CSS = """
<style>
:root {
  --teal: #0c8275; --teal-light: #e8f4f2; --bg: #faf9f5; --bg-sidebar: #f2f0eb;
  --bg-card: #ffffff; --border: #e4e1db; --border-med: #ccc9c2;
  --text: #1a1814; --text-2: #6b6459; --text-3: #a09890; --r: 8px; --r-lg: 12px;
  --amber: #d4880c; --red: #dc4040; --purple: #7c38b8; --blue: #3868c8;
}
.stApp { background: var(--bg) !important; }
section[data-testid="stSidebar"] {
  background: var(--bg-sidebar) !important; border-right: 1px solid var(--border) !important; box-shadow: none !important;
}
.block-container { padding-top: 3rem !important; max-width: none !important; }

.mg-section {
  font-size: 0.6rem; font-weight: 700; letter-spacing: 1.4px; text-transform: uppercase;
  color: var(--text-3); margin: 16px 0 6px; padding-bottom: 5px; border-bottom: 1px solid var(--border);
}
section[data-testid="stSidebar"] div[role="radiogroup"] label {
  display: flex !important; align-items: center !important; padding: 7px 10px !important;
  border-radius: var(--r) !important; margin-bottom: 2px !important; cursor: pointer !important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background: var(--teal) !important; }
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p { color: white !important; }
section[data-testid="stSidebar"] div[role="radiogroup"] label [data-baseweb="radio"] { display: none !important; }
section[data-testid="stSidebar"] div[role="radiogroup"] label p {
  font-size: 0.82rem !important; font-weight: 500 !important; color: var(--text) !important; margin: 0 !important;
}

.mg-nav {
  display: flex; align-items: center; justify-content: space-between;
  padding: 2px 0 16px; border-bottom: 1px solid var(--border); margin-bottom: 20px;
}
.mg-nav-brand { display: flex; align-items: center; gap: 10px; }
.mg-nav-title { font-size: 1rem; font-weight: 700; color: var(--text); font-family: -apple-system, sans-serif; }
.mg-badge {
  display: inline-block; background: #dcf5f1; color: #0c6b5e; padding: 3px 9px; border-radius: 20px;
  font-size: 0.62rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase;
}
.mg-nav-right { display: flex; align-items: center; gap: 6px; font-size: 0.78rem; color: var(--text-2); }

.mg-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 16px 0; }
.mg-stat { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 16px 18px; }
.mg-stat.hi { background: var(--teal); border-color: var(--teal); }
.mg-stat-val { font-size: 2rem; font-weight: 800; color: var(--text); line-height: 1; font-family: -apple-system, sans-serif; }
.mg-stat.hi .mg-stat-val { color: white; }
.mg-stat-lbl { font-size: 0.62rem; font-weight: 600; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.9px; margin-top: 6px; }
.mg-stat.hi .mg-stat-lbl { color: rgba(255,255,255,0.7); }

.mg-file-title { font-size: 1.1rem; font-weight: 700; color: var(--text); font-family: -apple-system, sans-serif; }
.mg-file-meta { font-size: 0.75rem; color: var(--text-3); font-family: monospace; }

.mg-finding {
  background: var(--bg-card); border: 1px solid var(--border); border-left: 3px solid var(--teal);
  border-radius: 0 var(--r) var(--r) 0; padding: 12px 16px; margin-bottom: 10px;
}
.mg-finding-hdr { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.mg-finding-cat { font-size: 0.82rem; font-weight: 700; color: var(--text); }
.mg-snippet { font-family: 'Courier New', monospace; font-size: 0.85rem; color: var(--text); background: #f6f4ef; padding: 4px 8px; border-radius: 5px; display: inline-block; }
.mg-why { font-size: 0.74rem; color: var(--text-2); margin-top: 6px; }
.mg-pill { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 0.62rem; font-weight: 700; }
.mg-pill.art { background: var(--teal-light); color: #0c6b5e; margin-right: 4px; }
.mg-pill.conf { background: #f2f0eb; color: var(--text-2); }
.mg-pill.det { background: #eef1f8; color: var(--blue); }

.mg-badge-retention { background: #fbeaea; color: var(--red); border: 1px solid #f3cccc; padding: 2px 9px; border-radius: 10px; font-size: 0.64rem; font-weight: 700; }
.mg-badge-ok { background: #eaf6f3; color: #0c6b5e; padding: 2px 9px; border-radius: 10px; font-size: 0.64rem; font-weight: 600; }
.mg-badge-src { background: #f2f0eb; color: var(--text-2); padding: 2px 9px; border-radius: 10px; font-size: 0.64rem; font-weight: 600; }
.mg-status-confirmed { color: #0c6b5e; font-weight: 700; font-size: 0.7rem; }
.mg-status-delete { color: var(--red); font-weight: 700; font-size: 0.7rem; }

@keyframes scanSweep { 0% { top: 0; opacity: 0.9; } 100% { top: calc(100% - 2px); opacity: 0.15; } }
.mg-scan { position: relative; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--r); padding: 16px; overflow: hidden; height: 60px; }
.mg-scan-beam { position: absolute; left: 0; top: 0; width: 100%; height: 2px;
  background: linear-gradient(90deg, transparent, var(--teal) 50%, transparent); animation: scanSweep 1.2s ease-in-out infinite alternate; }

.stButton > button { background: var(--bg-card) !important; border: 1px solid var(--border-med) !important; border-radius: var(--r) !important; color: var(--text) !important; font-weight: 500 !important; box-shadow: none !important; font-size: 0.8rem !important; }
.stButton > button:hover { border-color: var(--teal) !important; color: var(--teal) !important; }
.mg-footer { font-size: 0.7rem; color: var(--text-3); padding: 12px 0 0; border-top: 1px solid var(--border); margin-top: 24px; text-align: center; }
</style>
"""

CATEGORY_COLOR = {
    "name": "#e05c2a", "username": "#e05c2a", "email": "#3868c8", "phone": "#3868c8",
    "fax": "#3868c8", "signature": "#7c38b8", "photo_video": "#7c38b8",
    "home_address": "#d4880c", "billing_shipping_address": "#d4880c", "travel_history": "#d4880c",
    "passport": "#b8102e", "id_card": "#b8102e", "drivers_license": "#b8102e",
}


def esc(text: str) -> str:
    return _html.escape(str(text))


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def navbar(subtitle: str, right: str = "") -> None:
    st.markdown(
        f'<div class="mg-nav"><div class="mg-nav-brand">'
        f'<span style="font-size:1.1rem">🛡️</span>'
        f'<span class="mg-nav-title">GDPR Data Discovery</span>'
        f'<span class="mg-badge">{esc(subtitle)}</span></div>'
        f'<div class="mg-nav-right">{right}</div></div>',
        unsafe_allow_html=True,
    )


def stat_cards(cards: list[tuple[str, str, bool]]) -> None:
    """cards = [(value, label, highlight), ...]"""
    html = '<div class="mg-stats">'
    for value, label, hi in cards:
        cls = "mg-stat hi" if hi else "mg-stat"
        html += f'<div class="{cls}"><div class="mg-stat-val">{esc(value)}</div><div class="mg-stat-lbl">{esc(label)}</div></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def human_bytes(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f} {unit}" if unit != "B" else f"{int(f)} B"
        f /= 1024
    return f"{f:.1f} TB"
