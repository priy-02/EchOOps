# Hindsight memory boundary

EchoOps uses the official `hindsight-client` Python SDK. `backend/app/hindsight_service.py` is the only module that calls it. `HindsightService` provides Retain, Recall, and Reflect. The configured bank is persistent Hindsight memory; incident/simulator state is in process memory.

Set `HINDSIGHT_BASE_URL`, `HINDSIGHT_API_KEY`, and `HINDSIGHT_BANK_ID` in the backend environment. For the clean demonstration, configure a newly created, empty bank so the first Recall is genuinely empty. The service fails with a clear configuration error when credentials or bank ID are absent. It does not substitute seeded, JSON, or process-local memories.

On resolution, EchoOps submits the incident ID, service, symptoms, logs, hypothesis, investigation, each attempted action and outcome, root cause, resolution, lesson, future strategy, actions to avoid, and applicability conditions via Retain. Before each response plan, it runs Recall with the active service and symptom query. The planner only marks the decision memory-influenced when actual recalled text is relevant to payment/503/connection-pool experience and includes the prior restart/pool strategy.

The simulator reset endpoint clears only process-local incidents. It intentionally does not delete Hindsight memories. This prototype does not persist incident console state across API restarts and does not verify live cloud access without operator-provided credentials.