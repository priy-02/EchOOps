# EchoOps

**Every incident leaves an echo. Every response gets smarter.**

EchoOps is a focused incident-response prototype. It demonstrates one repeatable loop: investigate a simulated Payment API 503, use Hindsight Recall before recommending an action, record deterministic action outcomes, and Retain the resolved experience through the official Hindsight Python client. A later similar incident can recall the actual retained experience and adapt its plan.

All service telemetry and action results are synthetic. No production systems are contacted. Hindsight memory is real and external; there is no local-memory fallback. Without valid Hindsight configuration, Recall and Retain return a clear error.

## Architecture

```text
React + Vite console
        │ VITE_API_BASE_URL
        ▼
FastAPI (Render-ready)
  ├── deterministic incident simulator
  ├── response plan from actual Recall result
  └── isolated HindsightService
        │ official hindsight-client SDK
        ▼
Hindsight Cloud memory bank
```

`backend/app/hindsight_service.py` is the only Hindsight adapter. EchoOps sends resolved experience text through `retain` and searches the configured bank with `recall`. It uses the official Python client documented by Hindsight: [Python SDK](https://docs.dev.hindsight.vectorize.io/python-sdk/).

## Configure a real Hindsight bank

1. Create a Hindsight Cloud account and memory bank. Use a new, empty bank for the clean before/after demo.
2. Create an API key in Hindsight Cloud. Do not paste it into source code or commit it.
3. Copy `.env.example` to `backend/.env` and set `HINDSIGHT_API_KEY` and `HINDSIGHT_BANK_ID`. The base URL defaults to Hindsight Cloud.
4. Copy `frontend/.env.example` to `frontend/.env` if the API is not at `http://localhost:8000`.

The backend reports Hindsight configured status from environment presence. It does not claim successful connectivity until an actual Recall or Retain succeeds.

## Local setup

Requirements: Python 3.10+, Node.js, npm.

Backend terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Frontend terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. API health: `http://localhost:8000/health`; interactive API docs: `http://localhost:8000/docs`.

## Demo flow

For a clean first recall, use a fresh Hindsight bank.

1. Click **Run Incident #1** (INC-1042), then **Investigate**.
2. Click **Recall historical experience**. Hindsight should return no relevant experience for a new bank.
3. Generate the generic recommendation and simulate restart. It fails in the simulator.
4. Inspect the connection pool, then increase capacity. The incident resolves.
5. Click **Retain experience**. EchoOps sends the complete evidence, hypotheses, action outcomes, root cause, lesson, and strategy to Hindsight.
6. Click **Run similar Incident #2** (INC-1087), investigate, then **Recall again**.
7. Generate the recommendation. When actual recalled Hindsight text contains the relevant payment, restart, and pool experience, EchoOps recommends inspecting the pool first and labels the decision memory-influenced.
8. Inspect the pool, apply the learned pool remediation, and retain the second experience.
9. **Reset simulator** clears only in-process incidents. Hindsight memories are persistent and are not deleted. For repeating the no-memory first half, select a new empty Hindsight bank.

## Tests

Focused tests exercise the simulator and Hindsight call boundary with an SDK test double; they do not claim to test a live Hindsight account.

```powershell
cd backend
pytest -q
```

## Deployment

The root `render.yaml` describes a Render web service rooted at `backend`. Add Hindsight secrets in Render's environment settings and update `CORS_ALLOWED_ORIGINS` to the deployed Vercel origin. In Vercel, set the project root to `frontend` and `VITE_API_BASE_URL` to the Render API origin, with no `/api/v1` suffix. `frontend/vercel.json` configures the Vite build and SPA fallback.

Build locally with `cd frontend; npm run build`. Deployments are not performed by this repository setup. Do not report a deploy as verified until `/health`, frontend-to-API CORS, and the full two-incident Hindsight loop have been checked against deployed URLs.

## Limitations

Incident and simulator state is held in process memory and resets when the backend restarts. Hindsight is the persistent experience memory. The response planner uses transparent deterministic rules over actual Recall results; there is no external LLM call. Hindsight credentials, bank creation, cloud deployments, GitHub publication, and live cloud verification require operator setup.