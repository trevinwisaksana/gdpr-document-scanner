# GDPR Data Discovery — Frontend

The web UI for the Bosch GDPR data-discovery tool (TECHon hackathon). A **Next.js 14 + TypeScript + Tailwind** app designed to deploy to **Vercel**, talking to the FastAPI backend on **Google Cloud Run**.

It ships fully **demo-data-first**: every screen is interactive out of the box with a bundled, realistic dataset — no backend required to demo. Where the backend exposes live endpoints, the app uses them; otherwise it falls back to demo data automatically.

---

## Quick start

```bash
cd frontend
npm install
cp .env.example .env.local   # optional — see Configuration
npm run dev                  # http://localhost:3000
```

**Sign in** (no real auth — prototype):

| Username | Password | View |
|----------|----------|------|
| `admin`  | `admin`  | Admin (Data Protection Officer) dashboard |
| `user`   | `user`   | Employee — flagged files for Amara Okafor |

---

## Deploy to Vercel

1. Push this repo to GitHub.
2. In Vercel → **New Project** → import the repo.
3. Set **Root Directory** to `frontend/`. Framework auto-detects as Next.js.
4. (Optional) add the environment variables below.
5. Deploy. That's it — no server to manage.

> The backend stays on Google Cloud Run; only this `frontend/` folder goes to Vercel.

---

## Configuration

All env vars are optional. Without them, the app runs entirely on demo data.

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | _(empty)_ | Cloud Run base URL. When set, the app uses live endpoints where available (e.g. the Google Drive scan trigger) and falls back to demo data otherwise. |
| `NEXT_PUBLIC_DEMO_MODE` | `false` | Force demo mode even if an API base URL is set. |
| `NEXT_PUBLIC_OLLAMA_URL` | `http://localhost:11434` | Local Ollama endpoint for the "explain why flagged" summary (called from the browser). |
| `NEXT_PUBLIC_OLLAMA_MODEL` | `llama3.2` | Default Ollama model. Overridable per-user in Settings. |

### Backend reality check (verified against the live deployment)

The deployed Cloud Run image at `dashboard-http-…run.app` matches `app/main.py`. What's actually usable:

| Surface | Endpoint(s) | Status |
|---------|-------------|--------|
| Aggregate KPIs | `/kpis/total-files-registered \| -flagged \| -processed`, `/kpis/percentage-files-flagged` | ✅ live (Postgres `drive_files`) |
| Data owners | `/kpis/owners`, `/kpis/flagged-files-per-owner` | ✅ live |
| Live PII scan | `POST /scan/text` | ✅ live (regex → NER → LLM) |
| Trigger Drive scan | `POST /workflows/drive/scan` | ✅ live |
| Health | `GET /health` | ✅ live (note: **not** `/healthz`) |
| Per-user flagged files | `GET /users/{id}/files` | ⚠️ 500 — SQLite store not provisioned on Cloud Run |
| Finding decision | `PATCH /findings/{id}/status` | ⚠️ same SQLite store |

So the app is wired **hybrid**:

- **Admin / DPO surface is live** — the dashboard (`/admin`), data-owners table (`/admin/users`), and the live PII scanner (`/admin/scan`) read real data from the endpoints above, and the **"Scan Google Drive"** button triggers the real pipeline. If the backend is unreachable, these screens fall back to the bundled demo dataset and say so via a "Demo data" badge.
- **The employee workspace is a badged demo** — per-file findings, snippets, file text, decisions, and review stats have no live backing (`/users` + `/findings` 500, and there's no per-finding endpoint), so those screens run on the bundled dataset and are clearly marked "Demo data".

Configure the backend URL with `NEXT_PUBLIC_API_BASE_URL` (it defaults to the known deployment). Set `NEXT_PUBLIC_DEMO_MODE=true` to force demo data everywhere.

### Local AI summaries (Ollama)

The file viewer's **"Generate summary"** explains why a file was flagged using a local LLM. Because the summary runs on the *viewer's* machine, the browser calls Ollama directly — so allow the origin:

```bash
OLLAMA_ORIGINS=* ollama serve
ollama pull llama3.2
```

If Ollama isn't reachable, the app shows a clear, rule-based fallback summary instead.

---

## What's inside

```
frontend/
├── app/
│   ├── page.tsx                  Login (public)
│   ├── (app)/                    Authenticated shell (sidebar + route guard)
│   │   ├── files/                Employee: flagged-file explorer (multi-select)
│   │   │   └── [fileId]/         Employee: VS Code-style viewer (preview + PII + AI summary)
│   │   ├── stats/                Employee: personal review stats
│   │   ├── settings/             Employee: live preferences
│   │   └── admin/                Admin: dashboard, history, users, settings
├── components/                   Design-system primitives, charts, cards
└── lib/                          types, gdpr metadata, data selectors, api client,
                                  ollama client, and persisted session/decisions/settings stores
```

### Feature map (per the product spec)

**Employee**
- Landing file explorer of flagged files; multi-select to **delete / cancel (false positive) / extend retention**.
- VS Code-style viewer: file tree (left), document preview with highlighted PII (center), findings + Ollama "why flagged" summary (right). Prev/Next walk a **cyclic review list** — files you delete or cancel drop out; extended files stay.
- Switch between users' views (demo only, in the sidebar).
- Personal stats: assigned / pending / deleted / cancelled / extended.
- Working settings: density, snippet visibility, default sort, hide low-risk, Ollama model, notifications.

**Admin (live)**
- Dashboard: **real KPIs** (files registered / processed / flagged / % flagged / data owners), an outcome donut (flagged vs not-flagged vs unprocessed), a flagged-files-per-owner chart, the live **Scan Google Drive** trigger, and a **Refresh KPIs** button — all from the deployed backend.
- **Live PII scan**: paste text → real `regex → NER → LLM` findings from `POST /scan/text`, with per-detector toggles.
- Data owners: flagged-file exposure grouped by Drive owner (live `/kpis/*`).
- Scan history: per-run snapshots with a trend chart (**demo** — no live endpoint).
- Settings: source connectors, retention period, delta-scan frequency, and detection tuning (local prefs).

### State & persistence

Sign-in, review decisions, and settings are kept in `localStorage` (via React context providers in `lib/`), so the demo survives reloads. Review decisions map cleanly onto the backend's finding-status actions and are sent opportunistically (`PATCH /findings/{id}/status`) when that endpoint is live.

---

## Scripts

```bash
npm run dev     # dev server
npm run build   # production build (also typechecks)
npm run start   # serve the production build
npm run lint    # eslint
```

Built with Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts, and lucide-react.
