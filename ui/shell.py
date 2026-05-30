"""Shared visual shell — design system. IBM Plex Sans + IBM Plex Mono."""
from __future__ import annotations

import html as _html
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
:root {
  /* hex fallbacks — used when oklch is not supported */
  --accent:        #0891b2;
  --accent-strong: #0e7490;
  --accent-soft:   #ecfeff;
  --accent-line:   #a5f3fc;
  --bg:            #f8fafc;
  --surface:       #ffffff;
  --surface-alt:   #f4f7fb;
  --surface-2:     #eef2f7;
  --border:        #dde3ec;
  --border-soft:   #e8edf4;
  --text:          #1e2a3a;
  --text-muted:    #4f6480;
  --text-faint:    #7e92a8;
  --flag:          #d97706;
  --flag-soft:     #fffbeb;
  --flag-line:     #fde68a;
  --danger:        #dc2626;
  --danger-soft:   #fef2f2;
  --ok:            #16a34a;
  --ok-soft:       #f0fdf4;
  --ok-line:       #86efac;
  --shadow-sm: 0 1px 2px rgba(79,100,128,.06),0 1px 1px rgba(79,100,128,.04);
  --shadow-md: 0 4px 14px rgba(50,70,100,.08),0 1px 3px rgba(50,70,100,.05);
  --shadow-lg: 0 18px 48px rgba(40,60,90,.14);
}
@supports (color: oklch(0 0 0)) {
  :root {
    --accent:        oklch(0.55 0.15 205);
    --accent-strong: oklch(0.48 0.16 205);
    --accent-soft:   oklch(0.95 0.03 205);
    --accent-line:   oklch(0.86 0.05 205);
    --bg:            oklch(0.985 0.004 255);
    --surface:       oklch(1 0 0);
    --surface-alt:   oklch(0.972 0.005 255);
    --surface-2:     oklch(0.955 0.006 255);
    --border:        oklch(0.915 0.006 255);
    --border-soft:   oklch(0.945 0.005 255);
    --text:          oklch(0.27 0.02 262);
    --text-muted:    oklch(0.5 0.018 262);
    --text-faint:    oklch(0.63 0.014 262);
    --flag:          oklch(0.62 0.16 48);
    --flag-soft:     oklch(0.95 0.045 60);
    --flag-line:     oklch(0.86 0.07 60);
    --danger:        oklch(0.55 0.19 25);
    --danger-soft:   oklch(0.95 0.04 25);
    --ok:            oklch(0.58 0.11 158);
    --ok-soft:       oklch(0.95 0.035 158);
    --ok-line:       oklch(0.84 0.06 158);
    --shadow-sm: 0 1px 2px oklch(0.5 0.02 262/0.06),0 1px 1px oklch(0.5 0.02 262/0.04);
    --shadow-md: 0 4px 14px oklch(0.4 0.02 262/0.08),0 1px 3px oklch(0.4 0.02 262/0.05);
    --shadow-lg: 0 18px 48px oklch(0.35 0.03 262/0.14);
  }
}
html,body,[data-testid="stAppViewContainer"],[data-testid="stApp"]{
  font-family:"IBM Plex Sans",system-ui,sans-serif!important;
  background:var(--bg)!important;color:var(--text)!important;
}
.stApp{background:var(--bg)!important;}
*{box-sizing:border-box;}
.block-container{padding-top:0!important;max-width:none!important;}

/* ── sidebar ── */
section[data-testid="stSidebar"]{
  background:var(--surface)!important;
  border-right:1px solid var(--border)!important;
  box-shadow:none!important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label{
  display:flex!important;align-items:center!important;
  padding:8px 10px!important;border-radius:8px!important;
  margin-bottom:2px!important;cursor:pointer!important;
  font-family:"IBM Plex Sans",sans-serif!important;
  font-size:0.82rem!important;font-weight:500!important;
  color:var(--text-muted)!important;
  transition:background 0.12s,color 0.12s!important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){
  background:var(--accent-soft)!important;color:var(--accent-strong)!important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p{
  color:var(--accent-strong)!important;font-weight:600!important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label [data-baseweb="radio"]{display:none!important;}
section[data-testid="stSidebar"] div[role="radiogroup"] label p{
  font-size:0.82rem!important;font-weight:500!important;
  color:inherit!important;margin:0!important;
  font-family:"IBM Plex Sans",sans-serif!important;
}

/* ── topbar ── */
.ae-topbar{
  display:flex;align-items:center;gap:14px;
  padding:0 4px;height:58px;
  border-bottom:1px solid var(--border-soft);
  margin-bottom:26px;
}
.ae-topbar h1{
  font-size:1.5rem;font-weight:600;letter-spacing:-0.02em;
  margin:0;color:var(--text);font-family:"IBM Plex Sans",sans-serif;
}
.ae-topbar-right{margin-left:auto;display:flex;align-items:center;gap:10px;}
.ae-engine-tag{
  display:inline-flex;align-items:center;gap:7px;white-space:nowrap;
  font-family:"IBM Plex Mono",monospace;font-size:0.68rem;
  color:var(--text-muted);
  background:var(--surface);border:1px solid var(--border);
  padding:5px 10px;border-radius:999px;
}
.ae-engine-dot{
  width:6px;height:6px;border-radius:999px;
  background:var(--ok);box-shadow:0 0 0 3px var(--ok-soft);
  display:inline-block;flex:none;
}

/* ── section label ── */
.ae-section{
  display:flex;align-items:center;gap:9px;
  font-size:0.7rem;font-weight:600;letter-spacing:0.07em;
  text-transform:uppercase;color:var(--text-faint);
  margin:24px 0 12px;font-family:"IBM Plex Sans",sans-serif;
}
.ae-section::after{content:"";flex:1;height:1px;background:var(--border-soft);}

/* ── page header ── */
.ae-page-title{
  font-size:1.5rem;font-weight:600;letter-spacing:-0.02em;
  margin:0 0 6px;color:var(--text);font-family:"IBM Plex Sans",sans-serif;
}
.ae-page-sub{
  font-size:0.9rem;color:var(--text-muted);max-width:60ch;
  line-height:1.5;margin:0 0 22px;font-family:"IBM Plex Sans",sans-serif;
}

/* ── KPI grid ── */
.ae-kpi-grid{
  display:grid;grid-template-columns:repeat(5,1fr);
  gap:12px;margin-bottom:6px;
}
.ae-kpi{
  background:var(--surface);border:1px solid var(--border);
  border-radius:14px;padding:16px;box-shadow:var(--shadow-sm);
  display:flex;flex-direction:column;gap:3px;
  position:relative;overflow:hidden;
}
.ae-kpi-num{
  font-size:1.7rem;font-weight:600;letter-spacing:-0.03em;
  line-height:1.05;color:var(--text);font-family:"IBM Plex Sans",sans-serif;
}
.ae-kpi-num.mono{font-family:"IBM Plex Mono",monospace!important;font-size:1.45rem;}
.ae-kpi-num.accent{color:var(--accent-strong);}
.ae-kpi-num.flag{color:var(--flag);}
.ae-kpi-label{font-size:0.76rem;color:var(--text-muted);font-weight:500;font-family:"IBM Plex Sans",sans-serif;}
.ae-kpi-meta{font-size:0.68rem;color:var(--text-faint);margin-top:2px;font-family:"IBM Plex Mono",monospace;}
.ae-kpi-spark{position:absolute;right:0;top:0;bottom:0;width:4px;}
.ae-kpi-spark.accent{background:var(--accent);}
.ae-kpi-spark.flag{background:var(--flag);}

/* ── badges ── */
.ae-badge{
  display:inline-flex;align-items:center;gap:5px;
  font-size:0.68rem;font-weight:600;
  padding:2px 8px;border-radius:6px;border:1px solid transparent;
  white-space:nowrap;font-family:"IBM Plex Sans",sans-serif;
}
.ae-badge-src{background:var(--surface-alt);color:var(--text-muted);border-color:var(--border);font-family:"IBM Plex Mono",monospace!important;font-weight:500;font-size:0.66rem;}
.ae-badge-retention{background:var(--flag-soft);color:#b45309;border-color:var(--flag-line);}
.ae-badge-ok{background:var(--ok-soft);color:#15803d;border-color:var(--ok-line);}
.ae-article{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:0.66rem;font-weight:600;color:var(--accent-strong);background:var(--accent-soft);border:1px solid var(--accent-line);padding:1px 6px;border-radius:5px;}

/* ── employee strip ── */
.ae-strip{
  display:flex;align-items:center;gap:18px;
  background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:14px 20px;margin-bottom:26px;
  box-shadow:var(--shadow-sm);
}
.ae-strip-item{display:flex;align-items:baseline;gap:8px;}
.ae-strip-num{font-size:1.35rem;font-weight:600;letter-spacing:-0.02em;color:var(--text);font-family:"IBM Plex Sans",sans-serif;}
.ae-strip-num.flag{color:var(--flag);}
.ae-strip-num.ok{color:var(--ok);}
.ae-strip-lbl{font-size:0.8rem;color:var(--text-muted);font-family:"IBM Plex Sans",sans-serif;}
.ae-strip-sep{color:var(--border);font-size:1.1rem;}
.ae-strip-prog{margin-left:auto;display:flex;align-items:center;gap:10px;min-width:180px;}
.ae-strip-prog-track{flex:1;height:6px;background:var(--surface-2);border-radius:999px;overflow:hidden;}
.ae-strip-prog-fill{height:100%;background:var(--ok);border-radius:999px;}
.ae-strip-prog-pct{font-family:"IBM Plex Mono",monospace;font-size:0.72rem;color:var(--text-muted);font-weight:600;}

/* ── finding cards ── */
.ae-finding{
  border:1px solid var(--border);border-radius:11px;
  padding:14px 15px;margin-bottom:10px;background:var(--surface-alt);
}
.ae-finding-hdr{display:flex;align-items:center;gap:11px;margin-bottom:11px;flex-wrap:wrap;}
.ae-finding-type{font-size:0.84rem;font-weight:600;color:var(--text);font-family:"IBM Plex Sans",sans-serif;}
.ae-snippet{
  display:block;font-family:"IBM Plex Mono",monospace;font-size:0.76rem;
  background:var(--surface);border:1px solid var(--border);
  border-radius:8px;padding:10px 12px;color:var(--text);
  white-space:pre-wrap;word-break:break-word;line-height:1.5;
}
.ae-why{font-size:0.76rem;color:var(--text-muted);margin-top:10px;line-height:1.5;display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-family:"IBM Plex Sans",sans-serif;}

/* confidence */
.ae-conf{display:inline-flex;align-items:center;gap:7px;font-size:0.7rem;font-weight:600;font-family:"IBM Plex Mono",monospace;}
.ae-conf-bar{width:34px;height:5px;border-radius:999px;background:var(--surface-2);overflow:hidden;flex:none;}
.ae-conf-bar > i{display:block;height:100%;border-radius:999px;}
.ae-conf.likely{color:var(--danger);} .ae-conf.likely .ae-conf-bar > i{background:var(--danger);}
.ae-conf.possible{color:var(--flag);} .ae-conf.possible .ae-conf-bar > i{background:var(--flag);}
.ae-conf.low{color:var(--text-faint);} .ae-conf.low .ae-conf-bar > i{background:var(--text-faint);}

/* priority badges */
.ae-priority{display:inline-flex;align-items:center;gap:5px;font-size:0.66rem;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;padding:2px 8px;border-radius:5px;border:1px solid transparent;font-family:"IBM Plex Mono",monospace;}
.ae-priority-high  {background:#fef2f2;color:#b91c1c;border-color:#fca5a5;}
.ae-priority-medium{background:#fffbeb;color:#b45309;border-color:#fde68a;}
.ae-priority-low   {background:var(--surface-alt);color:var(--text-faint);border-color:var(--border);}

.ae-status-confirmed{color:#15803d;font-weight:600;font-size:0.72rem;background:var(--ok-soft);border:1px solid var(--ok-line);padding:2px 8px;border-radius:6px;font-family:"IBM Plex Sans",sans-serif;}
.ae-status-delete{color:var(--danger);font-weight:600;font-size:0.72rem;background:var(--danger-soft);border:1px solid var(--danger);padding:2px 8px;border-radius:6px;font-family:"IBM Plex Sans",sans-serif;}

/* ── scan panel ── */
.ae-scan-panel{
  display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  background:var(--surface);border:1px solid var(--border);
  border-radius:14px;padding:16px 18px;box-shadow:var(--shadow-sm);
  margin-bottom:20px;
}
.ae-scan-info{min-width:0;flex:1;}
.ae-scan-title{font-size:0.88rem;font-weight:600;color:var(--text);font-family:"IBM Plex Sans",sans-serif;}
.ae-scan-sub{font-size:0.76rem;color:var(--text-muted);margin-top:2px;font-family:"IBM Plex Sans",sans-serif;}

@keyframes scanSweep{0%{top:0;opacity:.9}100%{top:calc(100% - 2px);opacity:.15}}
.ae-scan-beam-wrap{position:relative;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;overflow:hidden;height:60px;}
.ae-scan-beam{position:absolute;left:0;top:0;width:100%;height:2px;
  background:linear-gradient(90deg,transparent,var(--accent) 50%,transparent);
  animation:scanSweep 1.2s ease-in-out infinite alternate;}

/* ── hbar chart ── */
.ae-hbar-row{display:grid;grid-template-columns:150px 1fr 44px;align-items:center;gap:12px;padding:5px 0;}
.ae-hbar-label{font-size:0.78rem;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:"IBM Plex Sans",sans-serif;}
.ae-hbar-track{height:9px;background:var(--surface-2);border-radius:999px;overflow:hidden;}
.ae-hbar-fill{height:100%;border-radius:999px;background:var(--flag);}
.ae-hbar-val{font-family:"IBM Plex Mono",monospace;font-size:0.74rem;color:var(--text);text-align:right;font-weight:500;}

/* source card */
.ae-src-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 14px;box-shadow:var(--shadow-sm);margin-bottom:10px;}
.ae-src-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px;}
.ae-src-name{font-family:"IBM Plex Mono",monospace;font-size:0.8rem;font-weight:500;color:var(--text);}
.ae-src-stat{font-family:"IBM Plex Mono",monospace;font-size:0.68rem;color:var(--text-faint);}
.ae-src-track{height:5px;background:var(--surface-2);border-radius:999px;overflow:hidden;}
.ae-src-fill{height:100%;background:var(--accent);border-radius:999px;}

/* ── login ── */
.ae-login-wrap{
  min-height:75vh;display:flex;align-items:center;justify-content:center;padding:24px;
}
.ae-login-card{
  width:100%;max-width:420px;
  background:var(--surface);border:1px solid var(--border);
  border-radius:18px;box-shadow:var(--shadow-lg);
  padding:30px 30px 26px;
}
.ae-login-mark{
  width:44px;height:44px;border-radius:12px;background:var(--accent);
  display:grid;place-items:center;color:white;box-shadow:var(--shadow-md);
  margin-bottom:18px;font-size:1.3rem;
}
.ae-login-title{font-size:1.3rem;font-weight:600;letter-spacing:-0.02em;color:var(--text);font-family:"IBM Plex Sans",sans-serif;margin:0 0 6px;}
.ae-login-sub{font-size:0.85rem;color:var(--text-muted);line-height:1.5;margin:0 0 22px;font-family:"IBM Plex Sans",sans-serif;}
.ae-login-pick{font-size:0.68rem;font-weight:600;letter-spacing:0.07em;text-transform:uppercase;color:var(--text-faint);margin-bottom:9px;font-family:"IBM Plex Sans",sans-serif;}
.ae-acct-list{display:flex;flex-direction:column;gap:7px;margin-bottom:20px;}
.ae-acct{
  display:flex;align-items:center;gap:12px;
  padding:10px 12px;border-radius:11px;
  border:1px solid var(--border);background:var(--surface);
  width:100%;text-align:left;font-family:inherit;
}
.ae-avatar{
  width:34px;height:34px;border-radius:999px;flex:none;
  display:flex;align-items:center;justify-content:center;
  font-size:0.72rem;font-weight:600;color:white;
  font-family:"IBM Plex Sans",sans-serif;
}
.ae-acct-name{font-size:0.86rem;font-weight:600;color:var(--text);font-family:"IBM Plex Sans",sans-serif;}
.ae-acct-role{font-size:0.72rem;color:var(--text-muted);font-family:"IBM Plex Sans",sans-serif;margin-top:1px;display:flex;align-items:center;gap:6px;}
.ae-role-tag{font-family:"IBM Plex Mono",monospace;font-size:0.64rem;padding:1px 6px;border-radius:5px;background:var(--surface-alt);border:1px solid var(--border);color:var(--text-muted);}
.ae-role-tag.admin{color:var(--accent-strong);background:var(--accent-soft);border-color:var(--accent-line);}
.ae-login-foot{font-size:0.7rem;color:var(--text-faint);text-align:center;margin-top:16px;line-height:1.5;font-family:"IBM Plex Sans",sans-serif;}

/* ── Streamlit component overrides ── */
.stButton > button{
  background:var(--surface)!important;border:1px solid var(--border)!important;
  border-radius:9px!important;color:var(--text)!important;
  font-weight:500!important;box-shadow:var(--shadow-sm)!important;
  font-size:0.8rem!important;font-family:"IBM Plex Sans",sans-serif!important;
  transition:background 0.12s,border-color 0.12s!important;
}
.stButton > button:hover{border-color:var(--text-faint)!important;background:var(--surface-alt)!important;}
[data-testid="baseButton-primary"]{background:var(--accent)!important;border-color:var(--accent)!important;color:white!important;}
[data-testid="baseButton-primary"]:hover{background:var(--accent-strong)!important;border-color:var(--accent-strong)!important;}

.stProgress > div > div{background:var(--surface-2)!important;border-radius:999px!important;}
.stProgress > div > div > div{border-radius:999px!important;}
.stProgress > div > div > div > div{background:var(--accent)!important;}

[data-baseweb="select"] > div{
  background:var(--surface)!important;border-color:var(--border)!important;
  border-radius:9px!important;font-family:"IBM Plex Sans",sans-serif!important;
  font-size:0.8rem!important;color:var(--text)!important;
}

[data-testid="stExpander"] details summary{
  font-family:"IBM Plex Sans",sans-serif!important;
  font-size:0.9rem!important;font-weight:600!important;color:var(--text)!important;
  background:var(--surface)!important;
  border:1px solid var(--border)!important;border-radius:13px!important;
  padding:12px 16px!important;
}
[data-testid="stExpander"] details[open] summary{border-radius:13px 13px 0 0!important;}
[data-testid="stExpander"] details > div:last-child{
  background:var(--surface)!important;
  border:1px solid var(--border)!important;border-top:none!important;
  border-radius:0 0 13px 13px!important;padding:12px 16px!important;
}

/* ── sidebar brand ── */
.ae-side-brand{display:flex;align-items:center;gap:10px;padding:18px 18px 16px;border-bottom:1px solid var(--border-soft);}
.ae-side-mark{width:30px;height:30px;border-radius:8px;background:var(--accent);display:grid;place-items:center;color:white;flex:none;font-size:0.85rem;}
.ae-side-brand-name{font-size:0.86rem;font-weight:600;letter-spacing:-0.01em;color:var(--text);font-family:"IBM Plex Sans",sans-serif;}
.ae-side-brand-sub{font-size:0.66rem;color:var(--text-faint);font-family:"IBM Plex Sans",sans-serif;}
.ae-side-group{font-size:0.62rem;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:var(--text-faint);padding:14px 10px 6px;font-family:"IBM Plex Sans",sans-serif;}

/* ── footer ── */
.ae-footer{font-size:0.7rem;color:var(--text-faint);padding:12px 0 0;border-top:1px solid var(--border);margin-top:24px;text-align:center;font-family:"IBM Plex Sans",sans-serif;}
</style>
"""

CATEGORY_COLOR = {
    "name": "#e05c2a", "username": "#e05c2a", "email": "#3868c8", "phone": "#3868c8",
    "fax": "#3868c8", "signature": "#7c38b8", "photo_video": "#7c38b8",
    "home_address": "#d4880c", "billing_shipping_address": "#d4880c", "travel_history": "#d4880c",
    "passport": "#b8102e", "id_card": "#b8102e", "drivers_license": "#b8102e",
}

_AVATAR_COLORS = [
    "#4f5bd5", "#d62976", "#962fbf", "#23a566", "#e07b39",
    "#2b7be9", "#6b4fbb", "#c1392b", "#2e86ab", "#b5451b",
]


def esc(v: str) -> str:
    return _html.escape(str(v))


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def avatar_color(name: str) -> str:
    return _AVATAR_COLORS[sum(ord(c) for c in name) % len(_AVATAR_COLORS)]


def avatar_initials(name: str) -> str:
    parts = name.split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[:2].upper()


def navbar(subtitle: str, right: str = "") -> None:
    right_html = (
        f'<div class="ae-engine-tag"><span class="ae-engine-dot"></span>{esc(right)}</div>'
        if right else ""
    )
    st.markdown(
        f'<div class="ae-topbar"><h1>{esc(subtitle)}</h1>'
        f'<div class="ae-topbar-right">{right_html}</div></div>',
        unsafe_allow_html=True,
    )


def section_label(text: str) -> None:
    st.markdown(f'<div class="ae-section">{esc(text)}</div>', unsafe_allow_html=True)


def kpi_grid(cards: list[dict]) -> None:
    html = '<div class="ae-kpi-grid">'
    for c in cards:
        v = c.get("variant", "")
        spark = f'<div class="ae-kpi-spark {v}"></div>' if v else ""
        meta = f'<div class="ae-kpi-meta">{esc(c["meta"])}</div>' if c.get("meta") else ""
        num_cls = f'ae-kpi-num{" " + v if v else ""}'
        html += (
            f'<div class="ae-kpi">'
            f'<div class="{num_cls}">{esc(c["num"])}</div>'
            f'<div class="ae-kpi-label">{esc(c["label"])}</div>'
            f'{meta}{spark}</div>'
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def stat_cards(cards: list[tuple[str, str, bool]]) -> None:
    kpi_grid([{"num": v, "label": l, "variant": "accent" if hi else ""} for v, l, hi in cards])


def human_bytes(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f} {unit}" if unit != "B" else f"{int(f)} B"
        f /= 1024
    return f"{f:.1f} TB"
