"""Isolated adapter for the official Hindsight Python client."""
import asyncio
import os
from typing import Any


class HindsightConfigurationError(RuntimeError):
    """Required Hindsight settings are absent or the SDK is unavailable."""


class HindsightOperationError(RuntimeError):
    """The configured Hindsight service rejected or failed an operation."""


class HindsightService:
    def __init__(self, base_url=None, api_key=None, bank_id=None, client=None):
        self.base_url = base_url if base_url is not None else os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
        self.api_key = api_key if api_key is not None else os.getenv("HINDSIGHT_API_KEY", "")
        self.bank_id = bank_id if bank_id is not None else os.getenv("HINDSIGHT_BANK_ID", "")
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.bank_id)

    def _get_client(self):
        if not self.configured:
            missing = [name for name, value in (("HINDSIGHT_API_KEY", self.api_key), ("HINDSIGHT_BANK_ID", self.bank_id)) if not value]
            raise HindsightConfigurationError("Hindsight is not configured. Set " + " and ".join(missing) + ".")
        if self._client is None:
            try:
                from hindsight_client import Hindsight
            except ImportError as exc:
                raise HindsightConfigurationError("Install the official hindsight-client package to use Hindsight.") from exc
            self._client = Hindsight(base_url=self.base_url, api_key=self.api_key, timeout=30.0)
        return self._client

    async def recall_similar_incidents(self, incident: dict[str, Any]) -> dict[str, Any]:
        query = (
            f"Resolved incident experience for {incident['service']} with symptoms "
            f"{', '.join(incident['symptoms'])}; HTTP 503, high traffic, connection errors. "
            "Find previous root causes, actions that failed, successful remediation, and lessons."
        )
        try:
            result = await self._get_client().arecall(
                bank_id=self.bank_id,
                query=query,
                budget="mid",
            )
            matches = [
                {
                    "id": getattr(item, "id", None),
                    "text": str(getattr(item, "text", item)),
                    "type": getattr(item, "type", None),
                    "metadata": getattr(item, "metadata", None) or {},
                }
                for item in (getattr(result, "results", None) or [])
            ]
            return {"query": query, "matches": matches, "source": "hindsight", "count": len(matches)}
        except HindsightConfigurationError:
            raise
        except Exception as exc:
            raise HindsightOperationError("Hindsight Recall failed. Check the bank, API key, and service status.") from exc

    async def retain_incident_experience(self, experience: dict[str, Any]) -> dict[str, Any]:
        content = "\n".join([
            f"EchoOps resolved incident experience: {experience['incident']}.",
            f"Incident: {experience['title']}; service: {experience['service']}; environment: {experience['environment']}.",
            f"Symptoms: {', '.join(experience['symptoms'])}.",
            f"Observed evidence: {'; '.join(experience['evidence'])}.",
            f"Initial hypothesis: {experience['initial_hypothesis']}.",
            f"Investigation: {experience['investigation']}.",
            f"Actions and outcomes: {'; '.join(experience['actions_attempted'])}.",
            f"Failed action: {experience['failed_action']}.",
            f"Successful action: {experience['successful_action']}.",
            f"Root cause: {experience['root_cause']}.",
            f"Resolution: {experience['resolution']}.",
            f"Lesson: {experience['lesson']}.",
            f"Future strategy: {experience['future_strategy']}.",
            f"Actions to avoid: {experience['actions_to_avoid']}.",
            f"Lesson applies when: {experience['applies_when']}.",
        ])
        try:
            result = await self._get_client().aretain(
                bank_id=self.bank_id,
                content=content,
                context="Resolved SRE incident and its verified action outcomes",
                metadata={"incident_id": str(experience["incident"]), "service": str(experience["service"]), "kind": "incident_experience"},
            )
            return {
                "retained": True,
                "source": "hindsight",
                "incident": experience["incident"],
                "operation_id": getattr(result, "operation_id", None),
            }
        except HindsightConfigurationError:
            raise
        except Exception as exc:
            raise HindsightOperationError("Hindsight Retain failed. The incident remains resolved, but its lesson was not stored.") from exc

    async def reflect_on_incident_history(self, incident: dict[str, Any]) -> dict[str, Any]:
        query = f"What response strategy applies to {incident['service']} HTTP 503 incidents with {', '.join(incident['symptoms'])}?"
        try:
            answer = await self._get_client().areflect(
                bank_id=self.bank_id,
                query=query,
                context="Choose an evidence-backed incident response. Include prior failed and successful actions.",
                budget="mid",
            )
            return {"text": str(getattr(answer, "text", answer)), "source": "hindsight"}
        except HindsightConfigurationError:
            raise
        except Exception as exc:
            raise HindsightOperationError("Hindsight Reflect failed. Check the bank, API key, and service status.") from exc

    async def aclose(self):
        if self._client is not None:
            close = getattr(self._client, "aclose", None)
            if close:
                await close()
            else:
                sync_close = getattr(self._client, "close", None)
                if sync_close:
                    await asyncio.to_thread(sync_close)


def get_memory_service() -> HindsightService:
    return HindsightService()