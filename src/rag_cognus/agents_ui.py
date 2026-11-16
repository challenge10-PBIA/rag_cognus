"""Aba 🧠 Agentes do app Streamlit: síntese de evidências e treino de apresentação."""

from __future__ import annotations

import hashlib

import mlflow
import streamlit as st

from rag_cognus import speech
from rag_cognus.agents.agents_judges import (
    COMMUNICATION_METRICS,
    EVIDENCE_METRICS,
    as_scores,
    judge_communication,
    judge_evidence,
    log_judgment,
    make_communication_judge,
    make_evidence_judge,
    reasons,
)
from rag_cognus.agents.communication import CommunicationAgent
from rag_cognus.agents.evidence import EvidenceAgent
from rag_cognus.agents.pipeline import synthesis_to_text
from rag_cognus.agents.schemas import AUDIENCES, CONTEXTS, AudienceProfile
from rag_cognus.config import Settings

MODES = ["🔎 Síntese de evidências", "🎯 Treinar apresentação"]
AUDIENCE_LABELS = {
    "leigo": "Público geral",
    "executivo": "Executivos e gestores",
    "academico": "Acadêmico",
    "estudante": "Estudantes",
    "saude": "Profissionais de saúde",
}
CONTEXT_LABELS = {
    "pitch": "Pitch",
    "aula": "Aula",
    "reuniao": "Reunião",
    "palestra": "Palestra",
    "entrevista": "Entrevista",
}
TONES = {"neutro": "Neutro", "formal": "Formal", "informal": "Informal"}
STRENGTH = {"forte": "🟢 forte", "moderada": "🟡 moderada", "fraca": "🟠 fraca"}
CONFIDENCE = {"alta": "🟢 alta", "media": "🟡 média", "baixa": "🔴 baixa"}


# Fábricas separadas para os testes trocarem os modelos por fakes.
def evidence_agent_for(retriever, settings: Settings) -> EvidenceAgent:
    return EvidenceAgent(retriever, settings)


def communication_agent_for(settings: Settings) -> CommunicationAgent:
    return CommunicationAgent(settings)


def evidence_judge_for(settings: Settings):
    return make_evidence_judge(settings)


def communication_judge_for(settings: Settings):
    return make_communication_judge(settings)


def _judge_and_log(kind: str, result: dict, settings: Settings, trace_id, mlflow_ok: bool):
    if kind == "evidence":
        judgment = judge_evidence(evidence_judge_for(settings), result)
    else:
        judgment = judge_communication(communication_judge_for(settings), result)
    if mlflow_ok:
        try:
            log_judgment(trace_id, judgment, settings.judge)
        except Exception as exc:
            st.toast(f"Notas não registradas no MLflow: {exc}")
    return {"scores": as_scores(judgment), "reasons": reasons(judgment)}


def _show_scores(judged: dict | None, metrics: dict):
    if not judged:
        return
    cols = st.columns(len(metrics))
    for col, (name, label) in zip(cols, metrics.items(), strict=True):
        col.metric(label, f"{judged['scores'][name]} / 5")
    with st.expander("Por que essas notas?"):
        for name, label in metrics.items():
            st.markdown(f"**{label}** — {judged['reasons'][name]}")


def _send_to_training():
    result = st.session_state["agent_evidence"]["result"]
    st.session_state["agent_mode"] = MODES[1]
    st.session_state["adapt_text"] = synthesis_to_text(result)
    st.session_state["adapt_claims"] = [c["text"] for c in result["synthesis"]["claims"]]


def render_evidence_agent(retriever, settings, niche, score, mlflow_ok):
    topic = st.text_area(
        "Tema",
        placeholder="Ex.: Como reduzir a ansiedade e melhorar a voz antes de um pitch?",
        max_chars=1000,
    )
    clicked = st.button("Analisar evidências", type="primary")
    if clicked and not topic.strip():
        st.warning("Escreva um tema para analisar.")
    elif clicked:
        try:
            with st.spinner("Dividindo o tema, buscando na Gold e sintetizando…"):
                result = evidence_agent_for(retriever, settings).run(topic, niche)
                trace_id = mlflow.get_last_active_trace_id() if mlflow_ok else None
                judged = (
                    _judge_and_log("evidence", result, settings, trace_id, mlflow_ok)
                    if score
                    else None
                )
            st.session_state["agent_evidence"] = {"result": result, "judged": judged}
        except Exception as exc:
            st.error(f"Não consegui concluir a análise. Confira se o Ollama está ativo. {exc}")
    state = st.session_state.get("agent_evidence")
    if not state:
        st.caption(
            "O agente divide o tema em subperguntas, busca evidências para cada uma e mostra "
            "o que a base sustenta, onde as fontes divergem e o que falta."
        )
        return
    result, synthesis = state["result"], state["result"]["synthesis"]
    st.markdown(f"#### {result['topic']}")
    st.caption(
        f"Confiança {CONFIDENCE[synthesis['confidence']]} · "
        f"{len(result['evidence'])} trechos · subperguntas: {' · '.join(result['subquestions'])}"
    )
    st.markdown(synthesis["summary"])
    _show_scores(state["judged"], EVIDENCE_METRICS)
    st.markdown("**Afirmações sustentadas**")
    if not synthesis["claims"]:
        st.caption("Nenhuma afirmação sustentada pelos trechos.")
    for claim in synthesis["claims"]:
        st.markdown(
            f"- {claim['text']}  \n  <small>{STRENGTH[claim['strength']]} · "
            f"{', '.join(claim['chunk_ids'])}</small>",
            unsafe_allow_html=True,
        )
    if result["discarded_claims"]:
        st.caption(
            f"{result['discarded_claims']} afirmação(ões) descartada(s) por citar fonte inválida."
        )
    left, right = st.columns(2)
    with left:
        st.markdown("**Conflitos entre fontes**")
        for item in synthesis["conflicts"] or ["Nenhum conflito apontado."]:
            st.markdown(f"- {item}")
    with right:
        st.markdown("**Lacunas na base**")
        for item in synthesis["gaps"] or ["Nenhuma lacuna apontada."]:
            st.markdown(f"- {item}")
    with st.expander(f"Trechos usados ({len(result['evidence'])})"):
        for hit in result["evidence"]:
            st.markdown(
                f"**{hit['chunk_id']}** · {hit['title']} · público: {hit['audience']}  \n"
                f"<small>{hit['subquestion']}</small>",
                unsafe_allow_html=True,
            )
            st.text(hit["text"])
            if hit["source_url"]:
                st.markdown(f"[Fonte]({hit['source_url']})")
    if synthesis["claims"]:
        st.button("Adaptar esta síntese para um público →", on_click=_send_to_training)


def render_communication_agent(settings, score, mlflow_ok, transcribe=None):
    c1, c2, c3, c4 = st.columns(4)
    audience = c1.selectbox(
        "Público", list(AUDIENCES), format_func=AUDIENCE_LABELS.get, key="adapt_audience"
    )
    context = c2.selectbox(
        "Contexto", list(CONTEXTS), index=3, format_func=CONTEXT_LABELS.get, key="adapt_context"
    )
    minutes = c3.number_input("Minutos", 0.5, 60.0, 3.0, step=0.5, key="adapt_minutes")
    tone = c4.selectbox("Tom", list(TONES), format_func=TONES.get, key="adapt_tone")
    if transcribe is not None:
        recording = st.audio_input("Grave sua fala para adaptá-la", key="adapt_voice")
        if recording is not None:
            audio = recording.getvalue()
            digest = hashlib.sha256(audio).hexdigest()
            if st.session_state.get("adapt_last_audio") != digest:
                st.session_state["adapt_last_audio"] = digest
                try:
                    with st.spinner("Transcrevendo sua fala…"):
                        st.session_state["adapt_text"] = transcribe(audio)
                    st.session_state["adapt_claims"] = []
                except Exception as exc:
                    st.warning(f"Não consegui transcrever o áudio: {exc}")
    else:
        st.caption("🎙️ " + speech.INSTALL_HINT)
    text = st.text_area(
        "Texto da sua apresentação",
        key="adapt_text",
        height=180,
        placeholder="Cole seu roteiro, grave sua fala acima ou traga uma síntese de evidências.",
    )
    clicked = st.button("Adaptar ao público", type="primary")
    if clicked and not text.strip():
        st.warning("Escreva, grave ou traga um texto para adaptar.")
    elif clicked:
        profile = AudienceProfile(audience=audience, context=context, minutes=minutes, tone=tone)
        claims = st.session_state.get("adapt_claims") or None
        try:
            with st.spinner("Adaptando o texto…"):
                result = communication_agent_for(settings).run(text, profile, claims)
                trace_id = mlflow.get_last_active_trace_id() if mlflow_ok else None
                judged = (
                    _judge_and_log("communication", result, settings, trace_id, mlflow_ok)
                    if score
                    else None
                )
            st.session_state["agent_communication"] = {"result": result, "judged": judged}
        except Exception as exc:
            st.error(f"Não consegui adaptar o texto. Confira se o Ollama está ativo. {exc}")
    state = st.session_state.get("agent_communication")
    if not state:
        return
    result = state["result"]
    after, before = result["metrics"], result["original_metrics"]
    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Tempo estimado",
        f"{after['estimated_minutes']:.1f} min",
        f"{after['time_deviation_minutes']:+.1f} min do alvo",
        delta_color="off",
    )
    m2.metric(
        "Legibilidade",
        f"{after['readability']:.0f} / 100",
        f"{after['readability'] - before['readability']:+.0f} vs. original",
    )
    m3.metric(
        "Palavras por frase",
        f"{after['avg_sentence_words']:.0f}",
        f"{after['avg_sentence_words'] - before['avg_sentence_words']:+.0f} vs. original",
        delta_color="inverse",
    )
    _show_scores(state["judged"], COMMUNICATION_METRICS)
    st.markdown("**Versão adaptada**")
    st.info(result["adapted"]["adapted_text"])
    left, right = st.columns(2)
    with left:
        st.markdown("**O que mudou**")
        for item in result["adapted"]["changes"] or ["—"]:
            st.markdown(f"- {item}")
    with right:
        st.markdown("**Dicas de ensaio**")
        for item in result["adapted"]["rehearsal_tips"] or ["—"]:
            st.markdown(f"- {item}")


def render_agents(retriever, settings, niche, score, mlflow_ok, transcribe=None):
    st.session_state.setdefault("agent_mode", MODES[0])
    mode = st.radio(
        "Agente", MODES, horizontal=True, key="agent_mode", label_visibility="collapsed"
    )
    if mode == MODES[0]:
        render_evidence_agent(retriever, settings, niche, score, mlflow_ok)
    else:
        render_communication_agent(settings, score, mlflow_ok, transcribe)
