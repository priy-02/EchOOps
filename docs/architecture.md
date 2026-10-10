# Architecture

The React/Vite console calls a FastAPI API. The backend keeps the deterministic payment incident simulator and response flow in `app.main`. Hindsight operations are isolated in `app.hindsight_service.HindsightService`, which uses the official `hindsight-client` SDK.

```text
React + Vite → FastAPI → incident simulator / response rules → HindsightService → Hindsight Cloud
```

Hindsight Retain stores completed incident experiences. Hindsight Recall returns memories before each response recommendation. The planner uses the actual returned memory text to decide whether the old failed restart and successful pool fix apply. Simulator incidents remain in-process and reset on restart; Hindsight is the persistent memory layer. The response planner is deterministic and explainable; there is no external LLM call.

Deployment files target Vercel for the frontend and Render for the API. API origin, CORS origins, Hindsight base URL, key, and bank ID are environment-configured. See README for local setup and required operator setup.