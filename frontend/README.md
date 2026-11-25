# Sahte Site Avcıları — Frontend

React 19 + TypeScript + Vite + Tailwind CSS (v4) + Lucide.
By default the app is in **live mode** and talks to the FastAPI backend in `../backend`.

## Quick start: `baslat.bat`

Double-click **`baslat.bat`** in the project root. It checks the requirements and free ports,
then opens two windows, **Backend (port 8000)** and **Frontend (port 5173)**.
Then open **http://localhost:5173**.

To stop the applications, press **Ctrl+C** in each window and close it. The launcher never stops
existing processes. If a port is already in use, it reports the process and starts nothing.
It installs nothing: run `npm install` (frontend) and `python -m pip install -r requirements.txt`
(backend) once beforehand, and fill in `backend\.env`.

## Running locally (Windows PowerShell)

To start the two applications by hand instead, start the backend first (see `backend/README.md` for its `.env`):

```powershell
cd C:\Users\<you>\Desktop\sahte_site_tespit\backend
python -m uvicorn app.main:app --reload --port 8000
```

Then the frontend, in a second terminal:

```powershell
cd C:\Users\<you>\Desktop\sahte_site_tespit\frontend
npm install          # first time only
npm run dev
```

| Application | Address |
| --- | --- |
| Frontend (Vite dev server) | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

The backend allows browser requests from `http://localhost:5173` and `http://127.0.0.1:5173` (`CORS_ORIGINS` in `backend/.env`).

Other commands:

```powershell
npm run build      # type-check and production build (dist/)
npm run preview    # serve the build at http://localhost:4173 (add this origin to CORS_ORIGINS to use it)
```

## Environment variables

Optional. Copy `.env.example` to `.env.local` (ignored by Git) to change them:

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend address |
| `VITE_ANALYSIS_MODE` | `live` | `live`: use the backend. `demo`: local sample data, no backend calls |

`VITE_` variables are embedded in the browser bundle. Never put database settings or secrets
here; MySQL settings live only in `backend/.env`.

## Live mode

- **Analysis:** `POST /api/analyze`, then `GET /api/result/{id}` is polled every 1.5 s while the
  analysis is queued or running. Polling stops on completion or failure, when you leave the page, or
  when another analysis is opened. After 3 minutes the page stops waiting and offers "Yeniden kontrol et".
  This frontend time limit is separate from the analysis status stored on the server.
- **History:** `GET /api/history` (search and result filter run on the server), with deletion of one
  record through `DELETE /api/analyses/{id}` after confirmation. "Clear all history" exists only in demo mode.
- **Analysis engine:** not implemented yet. The backend records each request as failed with
  `service_unavailable`, and the result page says so. No scores or findings are shown.

The request and response formats are documented in `backend/README.md`.

## Demo mode

Start with `VITE_ANALYSIS_MODE=demo` (for example in `.env.local`). A "Demo modu" bar is shown at the top, and the
home page lists sample addresses (reserved example domains) covering every result state. Demo results and demo
history are stored only in the browser (`localStorage`) and are never sent to or mixed with the backend history.

## Structure

```
src/
  types/analysis.ts      Shared types; mirror backend/app/schemas/analysis.py
  services/
    types.ts             AnalysisService interface, ServiceError codes
    apiService.ts        Live client (fetch, 15 s per-request timeout)
    index.ts             Picks live or demo
  demo/                  Demo provider, fixtures, demo-only local history
  hooks/                 useStartAnalysis, useAnalysisJob (polling), useHistoryQuery
  components/, pages/    Screens (unchanged design)
  lib/                   URL validation, formatting, Turkish labels
```
