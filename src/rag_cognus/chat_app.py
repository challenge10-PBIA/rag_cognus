"""Interface local: streamlit run src/rag_cognus/chat_app.py."""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv

from rag_cognus.chain import RagPipeline
from rag_cognus.config import Settings
from rag_cognus.evaluation import configure_tracking
from rag_cognus.gold import load_from_databricks, load_snapshot, save_snapshot
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


@st.cache_resource(show_spinner=False)
def prepare(snapshot: str, fingerprint: str, settings: Settings):
    # O fingerprint invalida o índice quando o snapshot é atualizado.
    documents = load_snapshot(snapshot)
    return GoldRetriever(documents, settings), len(documents)


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


def main():
    load_dotenv(ROOT / ".env")
    settings = Settings.from_env()
    snapshot = ROOT / ".cache/gold.jsonl"
    st.set_page_config(page_title="Cognus • teste seu RAG", page_icon="💬", layout="wide")
    st.title("Cognus")
    st.caption("Converse com a base de comunicação e confira as evidências recuperadas.")
    with st.sidebar:
        st.subheader("Sua consulta")
        niche_label = st.selectbox("Assunto", list(NICHES))
        backend_label = st.selectbox("Busca", ["Por termos · BM25", "Por significado · embeddings"])
        k = st.slider("Quantidade de trechos", 1, 10, settings.top_k)
        generate = st.toggle(
            "Gerar resposta com Qwen",
            value=True,
            help="Desative para inspecionar só a recuperação, sem esperar a geração.",
        )
        if st.button("Limpar conversa", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        with st.expander("Atualização da base"):
            st.caption("Atualiza o snapshot local a partir da Gold do Databricks.")
            if st.button("Atualizar Gold", use_container_width=True):
                try:
                    with st.spinner("Lendo a Gold…"):
                        docs = load_from_databricks(settings)
                        save_snapshot(docs, snapshot, settings.gold_view)
                    st.success(f"{len(docs)} trechos atualizados.")
                except Exception as exc:
                    st.error(f"Não foi possível atualizar a Gold: {exc}")
    if not snapshot.exists():
        st.info("Clique em “Atualização da base → Atualizar Gold” para carregar os documentos.")
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
        configure_tracking(settings)
    except Exception as exc:
        st.error(f"Não foi possível preparar a busca: {exc}")
        st.stop()
    st.sidebar.caption(f"Gold carregada · {count} trechos\n\nModelo · {settings.chat_model}")
    st.session_state.setdefault("messages", [])
    chat, sources = st.columns([1.2, 1], gap="large")
    with chat:
        st.subheader("Conversa")
        if not st.session_state.messages:
            st.info("Experimente: “Como organizar uma apresentação clara para meu público?”")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if message.get("elapsed") is not None:
                    st.caption(
                        f"{message['elapsed']:.1f}s · {message['mode']} · {message['niche']}"
                    )
        query = st.chat_input("Pergunte sobre comunicação, apresentações ou voz…", max_chars=3000)
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        try:
            with (
                chat,
                st.spinner(
                    "Consultando a Gold e preparando a resposta…"
                    if generate
                    else "Buscando trechos na Gold…"
                ),
            ):
                start = time.perf_counter()
                result = (
                    RagPipeline(retriever, config).predict(query, NICHES[niche_label])
                    if generate
                    else retrieve_only(retriever, query, NICHES[niche_label])
                )
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": result["response"],
                    "result": result,
                    "query": query,
                    "elapsed": time.perf_counter() - start,
                    "mode": backend_label,
                    "niche": niche_label,
                }
            )
        except Exception as exc:
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"Não consegui concluir esta consulta. Confira se o Ollama está ativo. Detalhe: {exc}",
                }
            )
        st.rerun()
    with sources:
        st.subheader("Evidências recuperadas")
        last = next((m for m in reversed(st.session_state.messages) if "result" in m), None)
        if not last:
            st.caption("Os trechos, as fontes e o público original aparecerão aqui.")
        else:
            st.caption("Pergunta: " + last.get("query", ""))
            result = last["result"]
            hits = result["retrieved_context"]
            cited = set(result.get("cited_chunk_ids", []))
            st.caption(f"{len(hits)} trechos recuperados · {len(cited)} citados na resposta")
            for index, hit in enumerate(hits, 1):
                meta = hit["metadata"]
                marker = " · citado" if hit["chunk_id"] in cited else ""
                with st.expander(
                    f"{index}. {meta.get('title', 'Documento')}{marker}", expanded=index == 1
                ):
                    st.text(hit["text"])
                    st.caption("Público: " + (meta.get("audience") or "não informado"))
                    st.caption("Nichos: " + ", ".join(json.loads(meta.get("nichos_json", "[]"))))
                    url = meta.get("source_url") or ""
                    if urlparse(url).scheme in {"http", "https"}:
                        st.link_button("Abrir fonte original", url)
                    st.code(hit["chunk_id"], language=None)
    st.caption(
        "Cada pergunta é avaliada separadamente; o histórico da tela não é usado como evidência."
    )


if __name__ == "__main__":
    main()
