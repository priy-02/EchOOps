from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main
from app.hindsight_service import HindsightService


class FakeHindsightClient:
    """Test double for verifying calls; production always uses the official SDK."""
    def __init__(self):
        self.memories = []
        self.recall_calls = []
        self.retain_calls = []

    async def arecall(self, *, bank_id, query, budget):
        self.recall_calls.append({"bank_id": bank_id, "query": query, "budget": budget})
        return SimpleNamespace(results=[
            SimpleNamespace(id=f"fact-{index}", text=text, type="experience", metadata={"incident_id": "INC-1042"})
            for index, text in enumerate(self.memories)
        ])

    async def aretain(self, *, bank_id, content, context, metadata):
        self.retain_calls.append({"bank_id": bank_id, "content": content, "context": context, "metadata": metadata})
        self.memories.append(content)
        return None


def first_incident(client):
    response = client.post("/api/v1/incidents", json={"incident_number": "INC-1042"})
    assert response.status_code == 200, response.text
    assert client.post("/api/v1/incidents/INC-1042/analyze").status_code == 200
    assert client.post("/api/v1/incidents/INC-1042/recall").status_code == 200
    plan = client.post("/api/v1/incidents/INC-1042/plan")
    assert plan.status_code == 200, plan.text
    assert plan.json()["recommendation"] == "Restart Payment Service"
    assert plan.json()["memory_influenced"] is False
    return plan.json()


def resolve_first_incident(client):
    first_incident(client)
    failed = client.post("/api/v1/incidents/INC-1042/actions", json={"action": "restart_service"})
    assert failed.status_code == 200 and failed.json()["status"] == "failed"
    inspected = client.post("/api/v1/incidents/INC-1042/actions", json={"action": "inspect_connection_pool"})
    assert inspected.status_code == 200
    success = client.post("/api/v1/incidents/INC-1042/actions", json={"action": "increase_connection_pool"})
    assert success.status_code == 200 and success.json()["status"] == "succeeded"
    retained = client.post("/api/v1/incidents/INC-1042/learn")
    assert retained.status_code == 200, retained.text
    return retained.json()


@pytest.fixture
def harness(monkeypatch):
    fake = FakeHindsightClient()
    monkeypatch.setattr(main, "memory", HindsightService(
        base_url="https://test.hindsight.invalid", api_key="test-key", bank_id="echoops-test", client=fake
    ))
    monkeypatch.setattr(main, "incidents", {})
    monkeypatch.setattr(main, "next_id", 1042)
    with TestClient(main.app) as client:
        yield client, fake


def test_incident_can_be_investigated(harness):
    client, _ = harness
    created = client.post("/api/v1/incidents", json={"incident_number": "INC-1042"}).json()
    result = client.post(f"/api/v1/incidents/{created['id']}/analyze")
    assert result.status_code == 200
    assert result.json()["current_evidence"]["symptoms"]


def test_hindsight_recall_is_called_with_incident_query(harness):
    client, fake = harness
    client.post("/api/v1/incidents", json={"incident_number": "INC-1042"})
    client.post("/api/v1/incidents/INC-1042/analyze")
    result = client.post("/api/v1/incidents/INC-1042/recall")
    assert result.status_code == 200
    assert len(fake.recall_calls) == 1
    assert "Payment API" in fake.recall_calls[0]["query"]
    assert result.json()["source"] == "hindsight"


def test_action_outcomes_and_root_cause_are_recorded(harness):
    client, _ = harness
    first_incident(client)
    failed = client.post("/api/v1/incidents/INC-1042/actions", json={"action": "restart_service"}).json()
    assert failed["status"] == "failed"
    assert client.post("/api/v1/incidents/INC-1042/actions", json={"action": "inspect_connection_pool"}).status_code == 200
    success = client.post("/api/v1/incidents/INC-1042/actions", json={"action": "increase_connection_pool"}).json()
    assert success["status"] == "succeeded"
    incident = client.get("/api/v1/incidents/INC-1042").json()
    assert incident["root_cause"] == "Database connection pool exhaustion"
    assert incident["status"] == "resolved"
    assert len(incident["actions"]) == 3


def test_resolved_experience_is_retained_in_hindsight(harness):
    client, fake = harness
    retained = resolve_first_incident(client)
    assert retained["retained"] is True
    assert retained["source"] == "hindsight"
    assert len(fake.retain_calls) == 1
    content = fake.retain_calls[0]["content"]
    assert "restart_service -> FAILURE" in content
    assert "increase_connection_pool -> SUCCESS" in content
    assert "Future strategy" in content


def test_second_similar_incident_adapts_from_recalled_experience(harness):
    client, fake = harness
    resolve_first_incident(client)
    client.post("/api/v1/incidents", json={"incident_number": "INC-1087"})
    client.post("/api/v1/incidents/INC-1087/analyze")
    recalled = client.post("/api/v1/incidents/INC-1087/recall").json()
    assert recalled["count"] > 0
    assert "INC-1042" in recalled["matches"][0]["text"]
    plan = client.post("/api/v1/incidents/INC-1087/plan").json()
    assert plan["memory_influenced"] is True
    assert plan["strategy_adapted"] is True
    assert plan["recommendation"] == "Inspect the database connection pool first"
    assert "restart" in plan["reason"].lower()
    assert len(fake.recall_calls) == 2


def test_missing_hindsight_configuration_returns_explicit_error(harness, monkeypatch):
    client, _ = harness
    monkeypatch.setattr(main, "memory", HindsightService(base_url="https://test.hindsight.invalid", api_key="", bank_id=""))
    client.post("/api/v1/incidents", json={"incident_number": "INC-1042"})
    client.post("/api/v1/incidents/INC-1042/analyze")
    response = client.post("/api/v1/incidents/INC-1042/recall")
    assert response.status_code == 503
    assert "Hindsight is not configured" in response.json()["detail"]


def test_reset_clears_simulator_but_preserves_hindsight_bank(harness):
    client, fake = harness
    resolve_first_incident(client)
    result = client.post("/api/v1/demo/reset").json()
    assert result["hindsight_memories_deleted"] is False
    assert client.get("/api/v1/incidents").json() == []
    assert fake.memories

def test_unrelated_hindsight_results_do_not_change_the_plan(harness):
    client, fake = harness
    fake.memories.append("A prior note says the user prefers weekly status updates.")
    client.post("/api/v1/incidents", json={"incident_number": "INC-1087"})
    client.post("/api/v1/incidents/INC-1087/analyze")
    recalled = client.post("/api/v1/incidents/INC-1087/recall").json()
    assert recalled["count"] == 1
    plan = client.post("/api/v1/incidents/INC-1087/plan").json()
    assert plan["memory_influenced"] is False
    assert plan["recommendation"] == "Restart Payment Service"

def test_health_does_not_claim_unconfigured_hindsight_is_connected(harness, monkeypatch):
    client, _ = harness
    monkeypatch.setattr(main, "memory", HindsightService(base_url="https://test.hindsight.invalid", api_key="", bank_id=""))
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["hindsight"] == {"configured": False, "provider": "Hindsight"}