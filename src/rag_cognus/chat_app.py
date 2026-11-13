"""Interface local: streamlit run src/rag_cognus/chat_app.py."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse

import altair as alt
import httpx
import mlflow
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from rag_cognus import speech
from rag_cognus.chain import RagPipeline
from rag_cognus.config import Settings
from rag_cognus.evaluation import EVAL_TAG, configure_tracking
from rag_cognus.gold import load_from_databricks, load_snapshot, save_snapshot
from rag_cognus.judges import METRICS, as_dict, judge_response, make_judge
from rag_cognus.retrieval import GoldRetriever

ROOT = Path(__file__).resolve().parents[2]
NICHES = {
    "Todos os nichos": None,
    "Apresentações e oratória": "apresentacoes_oratoria",
    "Comunicação assertiva e escuta": "assertividade_escuta",
    "Clareza e linguagem": "clareza_linguagem",
    "Voz e saúde vocal": "voz_saude_vocal",
    "Fluência e gagueira": "fluencia_gagueira",
    "Fonoaudiologia e contextos profissionais": "fono_contextos_profissionais",
}
# Paleta categórica validada (ordem fixa = cor fixa por métrica).
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
LABELS = list(METRICS.values())
COLOR_SCALE = alt.Scale(domain=LABELS, range=COLORS)
CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1300px;}
.chips {display:flex; flex-wrap:wrap; gap:.35rem; margin:.4rem 0 .2rem;}
.chip {font-size:.78rem; padding:.15rem .55rem; border-radius:999px;
       border:1px solid rgba(128,128,128,.35);}
.chip b {font-weight:600;}
.dot {display:inline-block; width:.55rem; height:.55rem; border-radius:50%; margin-right:.3rem;}
</style>
"""


@st.cache_resource(show_spinner=False)
def prepare(snapshot: str, fingerprint: str, settings: Settings):
    # O fingerprint invalida o índice quando o snapshot é atualizado.
    documents = load_snapshot(snapshot)
    return GoldRetriever(documents, settings), len(documents)


@st.cache_resource(show_spinner=False)
def judge_for(settings: Settings):
    return make_judge(settings)


@st.cache_resource(show_spinner="Carregando o Whisper local (1ª vez baixa o modelo)…")
def transcriber_for(model_name: str):
    return speech.load_transcriber(replace(Settings(), whisper_model=model_name))


def reachable(url: str) -> bool:
    try:
        return httpx.get(url, timeout=2).status_code < 400
    except httpx.HTTPError:
        return False


def metric_value(run, metric_name: str):
    if run is None:
        return None
    candidates = [
        f"metrics.{metric_name}",
        f"metrics.{metric_name}/mean",
        f"metrics.{metric_name}/value",
        metric_name,
    ]
    for key in candidates:
        if key in run:
            value = run.get(key)
            if value is not None and not pd.isna(value):
                return float(value)
    for key, value in run.items():
        key_text = str(key)
        if key_text.endswith(f".{metric_name}") or key_text.endswith(f".{metric_name}/mean"):
            if value is not None and not pd.isna(value):
                return float(value)
    return None


def retrieve_only(retriever, query, niche):
    docs = retriever.retrieve(query, niche)
    return {
        "response": f"Encontrei {len(docs)} {'trecho' if len(docs) == 1 else 'trechos'} para você conferir."
        if docs
        else "Não encontrei trechos com os filtros atuais. Tente outro nicho ou reformule a pergunta.",
        "retrieved_context": [
            {"chunk_id": d.id, "text": d.page_content, "metadata": d.metadata} for d in docs
        ],
        "cited_chunk_ids": [],
    }


def log_scores_to_trace(trace_id: str | None, judgment, judge_model: str):
    """Anexa as notas ao trace da resposta no MLflow (aparece na aba Traces)."""
    if not trace_id:
        return
    from mlflow.entities import AssessmentSource

    source = AssessmentSource(source_type="LLM_JUDGE", source_id=judge_model)
    mlflow.flush_trace_async_logging()  # o trace precisa estar salvo antes das notas
    for name in METRICS:
        item = getattr(judgment, name)
        mlflow.log_feedback(
            trace_id=trace_id, name=name, value=item.score, rationale=item.reason, source=source
        )


# ---------- gráficos ----------


def score_chips(scores: dict) -> str:
    chips = "".join(
        f'<span class="chip"><span class="dot" style="background:{COLORS[i]}"></span>'
        f"{label} <b>{scores[name]}</b>/5</span>"
        for i, (name, label) in enumerate(METRICS.items())
    )
    return f'<div class="chips">{chips}</div>'


def session_frame(messages: list[dict]) -> pd.DataFrame:
    rows = []
    for n, m in enumerate([m for m in messages if m.get("scores")], 1):
        for name, label in METRICS.items():
            rows.append(
                {"Pergunta": n, "Texto": m["query"], "Métrica": label, "Nota": m["scores"][name]}
            )
    return pd.DataFrame(rows)


def line_chart(df: pd.DataFrame, x: str, x_title: str, tooltip: list):
    base = alt.Chart(df).encode(
        x=alt.X(f"{x}:O", title=x_title, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Nota:Q", title="Nota média (1–5)", scale=alt.Scale(domain=[1, 5])),
        color=alt.Color("Métrica:N", scale=COLOR_SCALE, legend=alt.Legend(orient="bottom")),
        tooltip=tooltip,
    )
    return base.mark_line(strokeWidth=2) + base.mark_point(filled=True, size=70)


def bar_chart(means: dict):
    df = pd.DataFrame({"Métrica": LABELS, "Nota": [means.get(n) for n in METRICS]}).dropna()
    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4, height=18)
        .encode(
            y=alt.Y("Métrica:N", sort=LABELS, title=None),
            x=alt.X("Nota:Q", scale=alt.Scale(domain=[0, 5]), title="Nota média (1–5)"),
            color=alt.Color("Métrica:N", scale=COLOR_SCALE, legend=None),
            tooltip=["Métrica", alt.Tooltip("Nota:Q", format=".2f")],
        )
    )
    labels = bars.mark_text(align="left", dx=6).encode(
        text=alt.Text("Nota:Q", format=".1f"), color=alt.value("gray")
    )
    return (bars + labels).properties(height=40 * len(df) + 20)


def heatmap(table: pd.DataFrame):
    long = table.melt(
        id_vars=["case_id", "query"], value_vars=list(METRICS), var_name="m", value_name="Nota"
    ).dropna(subset=["Nota"])
    long["Métrica"] = long["m"].map(METRICS)
    return (
        alt.Chart(long)
        .mark_rect(stroke="white", strokeWidth=2, cornerRadius=3)
        .encode(
            x=alt.X("Métrica:N", sort=LABELS, title=None, axis=alt.Axis(labelAngle=-20)),
            y=alt.Y("case_id:N", title=None),
            color=alt.Color(
                "Nota:Q",
                scale=alt.Scale(domain=[1, 5], range=["#e6eefa", "#123d73"]),
                legend=alt.Legend(title="Nota"),
            ),
            tooltip=["case_id", "query", "Métrica", "Nota"],
        )
        .properties(height=max(120, 28 * long["case_id"].nunique()))
    )


# ---------- dados do MLflow ----------


@st.cache_data(ttl=30, show_spinner=False)
def eval_runs(tracking_uri: str, experiment: str) -> pd.DataFrame:
    mlflow.set_tracking_uri(tracking_uri)
    runs = mlflow.search_runs(
        experiment_names=[experiment],
        filter_string=f"tags.{EVAL_TAG} = 'true'",
        order_by=["attributes.start_time DESC"],
        max_results=50,
    )
    if runs.empty:
        return runs
    runs["label"] = (
        runs["tags.mlflow.runName"].fillna("run")
        + " · "
        + runs["start_time"].dt.strftime("%d/%m %H:%M")
    )
    return runs


@st.cache_data(ttl=300, show_spinner=False)
def per_case_table(tracking_uri: str, run_id: str) -> pd.DataFrame:
    mlflow.set_tracking_uri(tracking_uri)
    return mlflow.load_table("per_case.json", run_ids=[run_id])


# ---------- telas ----------


def render_chat(messages):
    if not messages:
        st.info("Experimente: “Como organizar uma apresentação clara para meu público?”")
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("scores"):
                st.markdown(score_chips(message["scores"]), unsafe_allow_html=True)
                with st.expander("Por que essas notas?"):
                    for name, label in METRICS.items():
                        st.markdown(f"**{label}** — {message['reasons'][name]}")
            if message.get("elapsed") is not None:
                result = message["result"]
                hits = len(result["retrieved_context"])
                cited = len(result.get("cited_chunk_ids", []))
                st.caption(
                    f"{message['elapsed']:.1f}s · {message['mode']} · {message['niche']} · "
                    f"{hits} trechos, {cited} citados (aba Evidências)"
                )


def render_evidence(messages):
    answered = [m for m in messages if "result" in m]
    if not answered:
        st.caption(
            "Faça uma pergunta na aba Conversa: os trechos recuperados, as fontes e o "
            "público original de cada resposta aparecerão aqui."
        )
        return
    # Mais recente primeiro; cada opção é uma pergunta da conversa.
    options = list(range(len(answered) - 1, -1, -1))
    pick, only_cited = st.columns([3, 1], vertical_alignment="bottom")
    chosen = pick.selectbox(
        "Pergunta",
        options,
        format_func=lambda i: f"{i + 1}. {answered[i]['query'][:90]}",
    )
    show_cited = only_cited.toggle("Só os citados")
    message = answered[chosen]
    result = message["result"]
    cited = set(result.get("cited_chunk_ids", []))
    hits = result["retrieved_context"]
    with st.container(border=True):
        st.markdown("**Resposta**")
        st.markdown(message["content"])
        st.caption(f"{len(hits)} trechos recuperados · {len(cited)} citados na resposta")
    if show_cited:
        hits = [h for h in hits if h["chunk_id"] in cited]
        if not hits:
            st.caption("Nenhum trecho foi citado nesta resposta.")
    for index, hit in enumerate(hits, 1):
        meta = hit["metadata"]
        marker = " · ✅ citado" if hit["chunk_id"] in cited else ""
        with st.expander(f"{index}. {meta.get('title', 'Documento')}{marker}", expanded=index == 1):
            st.text(hit["text"])
            st.caption("Público: " + (meta.get("audience") or "não informado"))
            st.caption("Nichos: " + ", ".join(json.loads(meta.get("nichos_json", "[]"))))
            url = meta.get("source_url") or ""
            if urlparse(url).scheme in {"http", "https"}:
                st.link_button("Abrir fonte original", url)
            st.code(hit["chunk_id"], language=None)


def render_metrics(settings: Settings, mlflow_ok: bool):
    st.markdown("#### Respostas desta conversa")
    df = session_frame(st.session_state.messages)
    if df.empty:
        st.caption(
            "Ative **Avaliar respostas** na barra lateral e faça perguntas: cada resposta "
            "recebe notas de 1 a 5 do juiz local."
        )
    else:
        means = df.groupby("Métrica")["Nota"].mean()
        cols = st.columns(len(METRICS))
        for col, label in zip(cols, LABELS):
            col.metric(label, f"{means[label]:.1f} / 5")
        if df["Pergunta"].nunique() > 1:
            st.altair_chart(
                line_chart(df, "Pergunta", "Pergunta nº", ["Pergunta", "Texto", "Métrica", "Nota"]),
                width="stretch",
            )
        else:
            st.altair_chart(
                bar_chart({n: means[label] for n, label in METRICS.items()}),
                width="stretch",
            )

    st.divider()
    st.markdown("#### Avaliações registradas no MLflow")
    if not mlflow_ok:
        st.warning(
            f"MLflow local fora do ar em {settings.tracking_uri}. Rode `rag-cognus mlflow-local`."
        )
        return
    runs = eval_runs(settings.tracking_uri, settings.experiment)
    judged = runs[runs["tags.judged"] == "true"] if "tags.judged" in runs else runs.iloc[0:0]
    if judged.empty:
        st.caption("Nenhuma avaliação com notas ainda. Rode no terminal:")
        st.code("rag-cognus evaluate --generate --judge --limit 5", language="bash")
        return
    choice = st.selectbox("Avaliação", judged["label"].tolist())
    run = judged[judged["label"] == choice].iloc[0]
    means = {n: metric_value(run, n) for n in METRICS}
    previous = judged[judged["start_time"] < run["start_time"]].head(1)
    cols = st.columns(len(METRICS) + 1)
    for col, (name, label) in zip(cols, METRICS.items()):
        current = means.get(name)
        previous_mean = metric_value(previous.iloc[0], name) if not previous.empty else None
        if current is None or pd.isna(current):
            value = "—"
            delta = None
        else:
            value = f"{float(current):.2f}"
            delta = None
            if previous_mean is not None and not pd.isna(previous_mean):
                delta = f"{float(current) - float(previous_mean):+.2f}"
        col.metric(label, value, delta=delta)
    errors = metric_value(run, "error")
    cols[-1].metric("Erros", f"{(errors or 0):.0%}")
    st.caption(
        f"Modelo {run.get('params.chat_model')} · juiz {run.get('params.judge_model')} · "
        f"busca {run.get('params.backend')} k={run.get('params.top_k')} · "
        f"{run.get('params.cases')} perguntas. Variação em relação à avaliação anterior."
    )

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("##### Evolução entre avaliações")
        history = judged.iloc[::-1].melt(
            id_vars=["label"],
            value_vars=[f"metrics.{n}/mean" for n in METRICS if f"metrics.{n}/mean" in judged],
            var_name="m",
            value_name="Nota",
        )
        history["Métrica"] = (
            history["m"].str.removeprefix("metrics.").str.removesuffix("/mean").map(METRICS)
        )
        history["Avaliação"] = history["label"]
        if judged.shape[0] > 1:
            st.altair_chart(
                line_chart(
                    history,
                    "Avaliação",
                    None,
                    ["Avaliação", "Métrica", alt.Tooltip("Nota:Q", format=".2f")],
                ),
                width="stretch",
            )
        else:
            st.altair_chart(bar_chart(means), width="stretch")
    with right:
        st.markdown("##### Notas por pergunta")
        try:
            table = per_case_table(settings.tracking_uri, run["run_id"])
            st.altair_chart(heatmap(table), width="stretch")
        except Exception as exc:
            st.caption(f"Tabela por pergunta indisponível: {exc}")
            table = None
    if table is not None:
        with st.expander("Ver tabela com respostas"):
            st.dataframe(table, width="stretch", hide_index=True)
    st.link_button(
        "Abrir esta avaliação no MLflow",
        f"{settings.tracking_uri}/#/experiments/{run['experiment_id']}/runs/{run['run_id']}",
    )


def main():
    load_dotenv(ROOT / ".env", override=True)
    settings = Settings.from_env()
    snapshot = ROOT / ".cache/gold.jsonl"
    st.set_page_config(page_title="Cognus · RAG", page_icon="💬", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    is_http = urlparse(settings.tracking_uri).scheme in {"http", "https"}
    mlflow_ok = reachable(settings.tracking_uri.rstrip("/") + "/health") if is_http else True
    ollama_ok = reachable(settings.ollama_url.rstrip("/") + "/api/tags")

    with st.sidebar:
        st.markdown("### Cognus")
        st.caption(
            f"{'🟢' if ollama_ok else '🔴'} Ollama · {settings.chat_model}  \n"
            f"{'🟢' if mlflow_ok else '🔴'} MLflow local · {settings.tracking_uri}"
        )
        if is_http and mlflow_ok:
            st.link_button("Abrir MLflow", settings.tracking_uri, width="stretch")
        st.divider()
        niche_label = st.selectbox("Assunto", list(NICHES))
        backend_label = st.selectbox("Busca", ["Por termos · BM25", "Por significado · embeddings"])
        k = st.slider("Quantidade de trechos", 1, 10, settings.top_k)
        generate = st.toggle(
            "Gerar resposta com Qwen",
            value=True,
            help="Desative para inspecionar só a recuperação, sem esperar a geração.",
        )
        score = st.toggle(
            "Avaliar respostas",
            value=False,
            disabled=not generate,
            help=f"O juiz ({settings.judge}) dá notas de 1 a 5 e registra no MLflow.",
        )
        if st.button("Limpar conversa", width="stretch"):
            st.session_state.messages = []
            st.rerun()
        with st.expander("Atualizar base"):
            try:
                via = (
                    "token (DATABRICKS_HOST)"
                    if settings.databricks_auth == "token"
                    else f"perfil {settings.profile}"
                )
            except ValueError as exc:
                via = str(exc)
            st.caption(f"Refaz o snapshot local a partir da Gold do Databricks · via {via}.")
            if st.button("Atualizar Gold", width="stretch"):
                try:
                    with st.spinner("Lendo a Gold…"):
                        docs = load_from_databricks(settings)
                        save_snapshot(docs, snapshot, settings.gold_view)
                    st.success(f"{len(docs)} trechos atualizados.")
                except Exception as exc:
                    st.error(f"Não foi possível atualizar a Gold: {exc}")

    if not snapshot.exists():
        st.info(
            "Abra **Atualizar base → Atualizar Gold** na barra lateral para carregar os documentos."
        )
        st.stop()
    try:
        manifest = json.loads(snapshot.with_suffix(".manifest.json").read_text())
        config = replace(
            settings,
            top_k=k,
            backend="dense" if backend_label.startswith("Por significado") else "bm25",
        )
        with st.spinner("Preparando a busca…"):
            retriever, count = prepare(str(snapshot), manifest["snapshot_sha256"], config)
    except Exception as exc:
        st.error(f"Não foi possível preparar a busca: {exc}")
        st.stop()
    if mlflow_ok:
        configure_tracking(settings)
    else:
        mlflow.tracing.disable()
    st.sidebar.caption(f"Gold carregada · {count} trechos")
    st.session_state.setdefault("messages", [])

    chat_tab, evidence_tab, metrics_tab = st.tabs(["💬 Conversa", "📚 Evidências", "📊 Métricas"])
    with chat_tab:
        chat_col = st.container()
        query = st.chat_input("Pergunte sobre comunicação, apresentações ou voz…", max_chars=3000)
        via = "text"
        if speech.available():
            recording = st.audio_input("Ou grave sua pergunta", key="voice")
            if recording is not None and not query:
                audio = recording.getvalue()
                digest = hashlib.sha256(audio).hexdigest()
                # st.audio_input mantém o áudio entre reruns: só transcreve gravação nova.
                if st.session_state.get("last_audio") != digest:
                    st.session_state["last_audio"] = digest
                    try:
                        with st.spinner("Transcrevendo sua pergunta…"):
                            query = speech.transcribe(
                                transcriber_for(settings.whisper_model), audio
                            )
                        via = "voice"
                    except Exception as exc:
                        st.warning(f"Não consegui transcrever o áudio: {exc}")
        else:
            st.caption("🎙️ " + speech.INSTALL_HINT)
        if query:
            st.session_state.messages.append(
                {"role": "user", "content": ("🎙️ " if via == "voice" else "") + query}
            )
            message = {
                "role": "assistant",
                "query": query,
                "mode": backend_label,
                "niche": niche_label,
                "via": via,
            }
            try:
                with chat_col, st.spinner("Consultando a Gold e preparando a resposta…"):
                    start = time.perf_counter()
                    trace_id = None
                    if generate:
                        result = RagPipeline(retriever, config).predict(query, NICHES[niche_label])
                        trace_id = mlflow.get_last_active_trace_id() if mlflow_ok else None
                    else:
                        result = retrieve_only(retriever, query, NICHES[niche_label])
                    message.update(
                        content=result["response"],
                        result=result,
                        elapsed=time.perf_counter() - start,
                    )
                    if trace_id:
                        try:
                            mlflow.flush_trace_async_logging()
                            mlflow.MlflowClient().set_trace_tag(trace_id, "input_mode", via)
                        except Exception:
                            pass  # a tag é informativa; não deve derrubar a resposta
                    if generate and score:
                        judgment = judge_response(judge_for(settings), query, result)
                        message["scores"] = as_dict(judgment)
                        message["reasons"] = {n: getattr(judgment, n).reason for n in METRICS}
                        if mlflow_ok:
                            try:
                                log_scores_to_trace(trace_id, judgment, settings.judge)
                            except Exception as exc:
                                st.toast(f"Notas não registradas no MLflow: {exc}")
            except Exception as exc:
                message["content"] = (
                    "Não consegui concluir esta consulta. Confira se o Ollama está ativo. "
                    f"Detalhe: {exc}"
                )
            st.session_state.messages.append(message)
            st.rerun()
        with chat_col:
            render_chat(st.session_state.messages)
        st.caption(
            "Cada pergunta é respondida separadamente; o histórico não é usado como evidência."
        )
    with evidence_tab:
        render_evidence(st.session_state.messages)
    with metrics_tab:
        render_metrics(settings, mlflow_ok)


if __name__ == "__main__":
    main()
