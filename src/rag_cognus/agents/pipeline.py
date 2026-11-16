"""Pipeline tema → evidências → texto adaptado ao público (handoff pela síntese)."""

from __future__ import annotations

import mlflow

from rag_cognus.agents.communication import CommunicationAgent
from rag_cognus.agents.evidence import EvidenceAgent
from rag_cognus.agents.schemas import AudienceProfile


def synthesis_to_text(evidence_result: dict) -> str:
    """Texto-base para o agente de comunicação: resumo + afirmações sustentadas."""
    synthesis = evidence_result["synthesis"]
    lines = [synthesis["summary"].strip()]
    lines += [f"- {claim['text']}" for claim in synthesis["claims"]]
    return "\n".join(line for line in lines if line)


class EvidenceToAudience:
    def __init__(self, evidence_agent: EvidenceAgent, communication_agent: CommunicationAgent):
        self.evidence_agent = evidence_agent
        self.communication_agent = communication_agent

    @mlflow.trace(name="evidence_to_audience", span_type="AGENT")
    def run(self, topic: str, profile: AudienceProfile, niche: str | None = None) -> dict:
        evidence = self.evidence_agent.run(topic, niche)
        claims = [claim["text"] for claim in evidence["synthesis"]["claims"]]
        communication = self.communication_agent.run(
            synthesis_to_text(evidence), profile, source_claims=claims
        )
        # Depois dos filhos: eles também marcam a tag "agent" no mesmo trace.
        mlflow.update_current_trace(tags={"agent": "pipeline", "audience": profile.audience})
        return {"evidence": evidence, "communication": communication}
