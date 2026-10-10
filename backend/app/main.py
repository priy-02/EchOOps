"""Focused EchoOps incident-learning workflow and deterministic simulator."""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .hindsight_service import (
    HindsightConfigurationError,
    HindsightOperationError,
    get_memory_service,
)

load_dotenv()

@asynccontextmanager
async def lifespan(_app):
    yield
    close = getattr(memory, "aclose", None)
    if close:
        await close()


app = FastAPI(title="EchoOps API", version="0.2.0", description="A simulated incident response workflow with real Hindsight memory", lifespan=lifespan)
origins = [value.strip() for value in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if value.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])
memory = get_memory_service()
incidents: dict[str, dict[str, Any]] = {}
next_id = 1042


class IncidentInput(BaseModel):
    scenario: str = "payment_api_503"
    incident_number: str | None = None


class ActionInput(BaseModel):
    action: str = Field(min_length=1, max_length=80)


class MemoryRecallInput(BaseModel):
    incident_number: str | None = None
    scenario: str = "payment_api_503"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_event(incident: dict, label: str, detail: str):
    incident["events"].append({"at": now_iso(), "label": label, "detail": detail})


def new_incident(number: str | None = None, scenario: str = "payment_api_503") -> dict:
    global next_id
    if number is None:
        number = f"INC-{next_id}"
        next_id += 1
    elif number in incidents:
        raise HTTPException(409, f"{number} already exists in this demo session")
    incident = {
        "id": number,
        "incident_number": number,
        "title": "Payment API returning HTTP 503",
        "description": "Elevated payment failures under peak traffic in the deterministic simulator.",
        "service": "Payment API",
        "environment": "simulated production",
        "severity": "critical",
        "status": "investigating",
        "scenario": scenario,
        "symptoms": ["HTTP 503", "High traffic", "Connection errors", "Elevated error rate"],
        "logs": ["09:42:11 gateway: upstream connection attempts timing out", "09:42:16 payment-api: HTTP 503 rate 18.4%"],
        "metrics": {"error_rate": 18.4, "requests_per_min": 12840, "pool_utilization": None, "p95_ms": 2450},
        "events": [],
        "actions": [],
        "root_cause": None,
        "resolution": None,
        "resolved_at": None,
        "analyzed": False,
        "recall_done": False,
        "recall": {"query": None, "matches": [], "source": "hindsight", "count": 0},
        "strategy_adapted": False,
        "recommendation": None,
        "retained": False,
        "created_at": now_iso(),
    }
    incidents[number] = incident
    add_event(incident, "Incident detected", "Payment API 503s observed in simulated telemetry")
    return incident


def find_incident(incident_id: str) -> dict:
    incident = incidents.get(incident_id)
    if incident is None:
        raise HTTPException(404, "Incident not found in this demo session")
    return incident


async def run_memory(operation):
    try:
        return await operation
    except HindsightConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HindsightOperationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/health")
@app.get("/api/v1/health")
def health():
    return {"status": "ok", "hindsight": {"configured": memory.configured, "provider": "Hindsight"}}


@app.get("/api/v1/incidents")
def list_incidents():
    return list(incidents.values())


@app.post("/api/v1/incidents")
def create_incident(body: IncidentInput):
    return new_incident(body.incident_number, body.scenario)


@app.get("/api/v1/incidents/{incident_id}")
def incident_detail(incident_id: str):
    return find_incident(incident_id)


@app.post("/api/v1/incidents/{incident_id}/analyze")
def investigate(incident_id: str):
    incident = find_incident(incident_id)
    incident["analyzed"] = True
    incident["status"] = "investigating"
    result = {
        "incident_id": incident_id,
        "current_evidence": {
            "symptoms": incident["symptoms"],
            "logs": incident["logs"],
            "metrics": incident["metrics"],
        },
        "hypotheses": [
            {"name": "Connection pool exhaustion", "confidence": 0.62, "status": "unconfirmed"},
            {"name": "Traffic spike", "confidence": 0.58, "status": "observed"},
        ],
        "initial_hypothesis": "Payment workers are unhealthy under peak load.",
        "reasoning_mode": "Deterministic simulator rules",
    }
    add_event(incident, "Investigation started", "Reviewed simulated logs, metrics, and symptoms")
    incident["analysis"] = result
    return result


@app.post("/api/v1/incidents/{incident_id}/recall")
async def recall(incident_id: str):
    incident = find_incident(incident_id)
    if not incident["analyzed"]:
        raise HTTPException(409, "Investigate the current incident before Hindsight Recall")
    recalled = await run_memory(memory.recall_similar_incidents(incident))
    incident["recall"] = recalled
    incident["recall_done"] = True
    if recalled["count"]:
        add_event(incident, "Hindsight Recall", f"Retrieved {recalled['count']} actual result(s) from the configured Hindsight bank")
    else:
        add_event(incident, "Hindsight Recall", "No relevant experience returned by the configured Hindsight bank")
    return recalled


@app.post("/api/v1/incidents/{incident_id}/reflect")
async def reflect(incident_id: str):
    incident = find_incident(incident_id)
    if not incident["recall_done"]:
        raise HTTPException(409, "Run Hindsight Recall before Reflect")
    return await run_memory(memory.reflect_on_incident_history(incident))


@app.post("/api/v1/incidents/{incident_id}/plan")
def recommend(incident_id: str):
    incident = find_incident(incident_id)
    if not incident["analyzed"]:
        raise HTTPException(409, "Investigate the incident before requesting a recommendation")
    if not incident["recall_done"]:
        raise HTTPException(409, "Hindsight Recall must finish before a recommendation is generated")

    recalled_text = " ".join(match["text"] for match in incident["recall"]["matches"]).casefold()
    relevant = bool(incident["recall"]["matches"]) and any(term in recalled_text for term in ("payment", "503", "connection pool"))
    previous_failure = relevant and "restart" in recalled_text and any(term in recalled_text for term in ("fail", "unsuccessful", "did not resolve", "did not fix"))
    previous_success = relevant and "pool" in recalled_text and any(term in recalled_text for term in ("success", "resolved", "increased", "increase"))
    learned_outcomes = previous_failure and previous_success
    incident["strategy_adapted"] = bool(learned_outcomes)
    plan = {
        "incident_id": incident_id,
        "current_evidence": "Payment API HTTP 503s, high traffic, and connection errors in simulated telemetry.",
        "historical_evidence": incident["recall"]["matches"] if relevant else [],
        "previous_approach_failed": "Restarting the service failed in the recalled experience." if previous_failure else None,
        "previous_resolution_succeeded": "Increasing connection-pool capacity succeeded in the recalled experience." if previous_success else None,
        "strategy_adapted": bool(learned_outcomes),
        "memory_influenced": bool(learned_outcomes),
        "recommendation": "Inspect the database connection pool first" if learned_outcomes else "Restart Payment Service",
        "steps": ["Inspect connection-pool utilization", "Compare current traffic with baseline", "Increase pool capacity if exhaustion is confirmed"] if learned_outcomes else ["Restart Payment Service", "Recheck error rate and connection health"],
        "reason": "Hindsight recalled a similar Payment API experience: restarting failed, while increasing pool capacity resolved it. Inspect pool health first." if learned_outcomes else "No relevant prior failure-and-resolution experience was returned by Hindsight, so the simulator uses its generic first response.",
        "expected_result": "Restore payment requests without repeating the previously failed restart." if learned_outcomes else "Restart workers and check whether the 503 rate drops.",
        "risk": "Low; inspect metrics before applying the simulated capacity change." if learned_outcomes else "Medium; a restart can interrupt in-flight requests and may not fix exhausted connections.",
        "confidence": 0.91 if learned_outcomes else 0.72,
    }
    incident["recommendation"] = plan
    add_event(incident, "Recommendation generated", "Decision adapted using Hindsight" if learned_outcomes else "Generic first response; no relevant Hindsight experience")
    return plan


@app.post("/api/v1/incidents/{incident_id}/actions")
def simulate_action(incident_id: str, body: ActionInput):
    incident = find_incident(incident_id)
    if not incident["recommendation"]:
        raise HTTPException(409, "Generate a recommendation before simulating an action")
    action = body.action.strip()
    if action not in {"restart_service", "inspect_connection_pool", "increase_connection_pool"}:
        raise HTTPException(422, "Unsupported action for the payment API simulator")
    if action == "restart_service":
        status, result = "failed", "Payment API continued returning 503; restart did not relieve connection exhaustion."
        incident["logs"].append("09:46:02 simulator: restart completed; upstream 503s persist")
        incident["metrics"]["pool_utilization"] = 100
        incident["root_cause"] = "Database connection pool exhaustion"
        add_event(incident, "Connection pool exhaustion identified", "Restart did not resolve saturated connection capacity")
    elif action == "inspect_connection_pool":
        status, result = "succeeded", "Pool is at 100% utilization; connection capacity is exhausted."
        incident["metrics"]["pool_utilization"] = 100
        incident["root_cause"] = "Database connection pool exhaustion"
        incident["logs"].append("09:47:10 simulator: connection pool at maximum capacity")
    else:
        status, result = "succeeded", "Pool capacity increased; payment API error rate returned to baseline."
        incident["metrics"]["pool_utilization"] = 64
        incident["metrics"]["error_rate"] = 0.2
        incident["metrics"]["p95_ms"] = 180
        incident["root_cause"] = "Database connection pool exhaustion"
        incident["resolution"] = "Increased database connection-pool capacity"
        incident["status"] = "resolved"
        incident["resolved_at"] = now_iso()
        add_event(incident, "Incident resolved", "Pool remediation succeeded in the deterministic simulator")
    action_record = {
        "id": f"{incident_id}-ACTION-{len(incident['actions']) + 1}",
        "incident_id": incident_id,
        "action": action,
        "reason": incident["recommendation"]["reason"],
        "status": status,
        "result": result,
        "created_at": now_iso(),
    }
    incident["actions"].append(action_record)
    add_event(incident, "Action outcome recorded", f"{action.replace('_', ' ')}: {status.upper()}")
    return action_record


@app.post("/api/v1/incidents/{incident_id}/outcome")
def outcome(incident_id: str):
    incident = find_incident(incident_id)
    return {"incident": incident, "outcome": "recorded" if incident["actions"] else "no_action_yet"}


@app.post("/api/v1/incidents/{incident_id}/learn")
async def retain(incident_id: str):
    incident = find_incident(incident_id)
    if incident["status"] != "resolved":
        raise HTTPException(409, "Resolve the incident before retaining its experience")
    if not any(action["status"] == "succeeded" for action in incident["actions"]):
        raise HTTPException(409, "A successful action outcome is required before retaining")
    if incident["retained"]:
        return {"retained": True, "source": "hindsight", "incident": incident_id, "already_retained": True}
    failed = [f"{action['action']} -> FAILURE: {action['result']}" for action in incident["actions"] if action["status"] == "failed"]
    succeeded = [f"{action['action']} -> SUCCESS: {action['result']}" for action in incident["actions"] if action["status"] == "succeeded"]
    experience = {
        "incident": incident_id,
        "title": incident["title"],
        "service": incident["service"],
        "environment": incident["environment"],
        "symptoms": incident["symptoms"],
        "evidence": incident["logs"],
        "initial_hypothesis": incident["analysis"]["initial_hypothesis"],
        "investigation": "Reviewed simulated logs and metrics; connection-pool saturation was confirmed after checking the action outcomes.",
        "actions_attempted": failed + succeeded,
        "failed_action": "; ".join(failed) or "None",
        "successful_action": "; ".join(succeeded),
        "root_cause": incident["root_cause"] or "Not established",
        "resolution": incident["resolution"] or "Not established",
        "lesson": "For Payment API HTTP 503s with connection errors, a service restart alone can fail when the database connection pool is exhausted. Inspect pool health and increase capacity when confirmed.",
        "future_strategy": "Inspect pool utilization, compare traffic, check deployment history, and apply pool remediation if exhaustion is confirmed.",
        "actions_to_avoid": "Do not repeat a blind service restart when matching evidence points to connection-pool exhaustion.",
        "applies_when": "Payment API returns HTTP 503 under high traffic with connection errors or saturated connection-pool metrics.",
    }
    saved = await run_memory(memory.retain_incident_experience(experience))
    incident["retained"] = True
    add_event(incident, "Lesson retained in Hindsight", "Resolved incident experience submitted to the configured Hindsight bank")
    return saved


@app.post("/api/v1/demo/run")
def run_demo(body: IncidentInput):
    return new_incident(body.incident_number, body.scenario)


@app.post("/api/v1/demo/reset")
def reset_demo():
    """Reset simulator incidents only. Persistent Hindsight memories are not deleted."""
    global next_id
    incidents.clear()
    next_id = 1042
    return {"reset": True, "hindsight_memories_deleted": False, "message": "Simulator reset. Hindsight memory remains persistent."}


@app.post("/api/v1/simulator/incidents")
def simulate_incident(body: IncidentInput):
    return new_incident(body.incident_number, body.scenario)


@app.get("/api/v1/simulator/logs")
def simulator_logs():
    return {"simulated": True, "logs": [line for incident in incidents.values() for line in incident["logs"]]}


@app.get("/api/v1/simulator/metrics")
def simulator_metrics():
    return {"simulated": True, "metrics": [incident["metrics"] for incident in incidents.values()]}