# FRONTEND
all the backend with the api will be deployed on google cloud only the frontend part will be deployed on the vercel so choose the tech stack for the frontend accordinly

## SIMPLE SIGN PAGE

(user, password): (admin, admin) open admin view and for (user, user) open user view

## USER VIEW

1. landing page: file explorer to view listing of all the flagged files
    - option/buttons to select multiple files for deletion, cancelling if false positive, and extend the retention period
2. File viewer page: click to open and preview a file (file explorer still stays in the side bar like vscode)
    1. buttons for previous, next, delete, cancel, extend (all the listing stored in cyclic list and removing only the ones for which decision is made i.e. delete or cancel)
    2. list PII entity found in the file and an option to generate summary using local ollama LLM to generate a very small explaination why the file was flagged using the data already available like file text and PII entity found (all of this has to be in file viewer page next to the file in the side bar on the right)
    3. option to switch to other user's view (just for demo because we are not doing access management and authetication)
3. Info/stats page for the user
    1. individual stat number of files total number of files assigned, deleted, pending, cancelled, extended
4. settings page [BE CREATIVE HERE AND PUT SOME MEANINGFUL WORKING SETTINGS FOR THE USER]


## ADMIN VIEW

1. landing page: dashboard with basic KPIs
    1. progress bar during the ongoing scan(% of remaining file/total number of files)
    2. pie chart or bar chart for total number of files: split/pie for flagged and not flagged, pending, cancelled, extension of retention (show numbers in percentage as well as volume of data in KB/MB/GB/TB) for most recent scan
2. history pagw: logs of previous scans with the stats captured just before the new scan (same as user page but just need to add numbers)
3. user page: list of all the users along with the stats for the selected scan
4. settings page [BE CREATIVE HERE AND PUT SOME MEANINGFUL WORKING SETTINGS FOR THE ADMIN]
    1. connectors settings
    2. selecting the retention period
    3. selecting delta scan frequency(daily, weekly, monthly, specific custom data and time)

---

## Implementation

Built in [`frontend/`](frontend/) — a **Next.js 14 + TypeScript + Tailwind** app that deploys to **Vercel** (set the project root to `frontend/`). See [`frontend/README.md`](frontend/README.md) for run/deploy/config details.

- **Sign in:** `admin`/`admin` → admin view, `user`/`user` → employee view.
- **Demo-first:** every screen is fully interactive on a bundled dataset. The live `POST /workflows/drive/scan` endpoint is wired for real; the other (not-yet-deployed) backend routes are used automatically once live.
- **Local AI summary:** the file viewer calls a local Ollama (`OLLAMA_ORIGINS=* ollama serve`) with a rule-based fallback.
- Every spec item above is implemented; review decisions, settings, and session persist in `localStorage`.