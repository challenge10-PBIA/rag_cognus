"""Pipeline tema → evidências → texto adaptado ao público (handoff pela síntese)."""

from __future__ import annotations

import mlflow

from rag_cognus.agents.communication import CommunicationAgent
from rag_cognus.agents.evidence import EvidenceAgent, synthesis_text
from rag_cognus.agents.schemas import AudienceProfile
from rag_cognus.llm import trace_tags


def synthesis_to_text(evidence_result: dict) -> str:
    """Texto-base para o agente de comunicação: resumo + afirmações sustentadas."""
    return synthesis_text(evidence_result["synthesis"])


class EvidenceToAudience:
    def __init__(self, evidence_agent: EvidenceAgent, communication_agent: CommunicationAgent):
        self.evidence_agent = evidence_agent
        self.communication_agent = communication_agent

    def run(self, topic: str, profile: AudienceProfile, niche: str | None = None) -> dict:
        """Devolve o dict completo; o span raiz recebe só o que os juízes leem (spec 011)."""
        with mlflow.start_span(name="evidence_to_audience", span_type="AGENT") as span:
            span.set_inputs({"topic": topic, "profile": profile.model_dump(), "niche": niche})
            evidence = self.evidence_agent.run(topic, niche)
            claims = [claim["text"] for claim in evidence["synthesis"]["claims"]]
            communication = self.communication_agent.run(
                synthesis_to_text(evidence), profile, source_claims=claims
            )
            response = communication["adapted"]["adapted_text"]
            cited = [c for claim in evidence["synthesis"]["claims"] for c in claim["chunk_ids"]]
            span.set_outputs(
                {
                    "response": response,
                    "evidence_summary": evidence["synthesis"]["summary"],
                    "cited_chunk_ids": list(dict.fromkeys(cited)),
                }
            )
            # Depois dos filhos: eles também marcam flow/agent e as prévias no mesmo trace.
            tags = trace_tags(self.evidence_agent.settings, "pipeline")
            tags |= {"agent": "pipeline", "audience": profile.audience}
            mlflow.update_current_trace(tags=tags, request_preview=topic, response_preview=response)
        return {"evidence": evidence, "communication": communication}
