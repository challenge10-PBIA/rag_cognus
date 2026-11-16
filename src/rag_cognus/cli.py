from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

from rag_cognus.agents.schemas import AUDIENCES, CONTEXTS
from rag_cognus.config import Settings


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def run_agents(args, settings: Settings, retriever, text: str | None = None):
    """Comandos synthesize/adapt: imprime o resultado (e as notas, com --judge) em JSON."""
    from rag_cognus.agents import agents_judges as aj
    from rag_cognus.agents.communication import CommunicationAgent
    from rag_cognus.agents.evidence import EvidenceAgent
    from rag_cognus.agents.pipeline import EvidenceToAudience
    from rag_cognus.agents.schemas import AudienceProfile

    if args.command == "synthesize":
        result = EvidenceAgent(retriever, settings).run(args.topic, args.niche)
        if args.judge:
            judge = aj.make_evidence_judge(settings)
            result["scores"] = aj.as_scores(aj.judge_evidence(judge, result))
    else:
        profile = AudienceProfile(
            audience=args.audience, context=args.context, minutes=args.minutes, tone=args.tone
        )
        communication = CommunicationAgent(settings)
        if args.topic:
            pipeline = EvidenceToAudience(EvidenceAgent(retriever, settings), communication)
            result = pipeline.run(args.topic, profile, args.niche)
            adapted = result["communication"]
        else:
            result = adapted = communication.run(text, profile)
        if args.judge:
            judge = aj.make_communication_judge(settings)
            result["scores"] = aj.as_scores(aj.judge_communication(judge, adapted))
    print(json.dumps(result, ensure_ascii=False, indent=2))


def serve_api(host: str, port: int):
    import mlflow
    import uvicorn

    from rag_cognus.api.app import Services, create_app
    from rag_cognus.evaluation import configure_tracking

    settings = Settings.from_env()
    try:
        configure_tracking(settings)
    except Exception as exc:  # sem MLflow a API funciona; só os traces ficam de fora
        print(f"Aviso: MLflow indisponível ({exc}); traces desativados.")
        mlflow.tracing.disable()
    print(f"Cognus API em http://{host}:{port}  (documentação: /docs)")
    uvicorn.run(create_app(Services(settings)), host=host, port=port)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Cognus: Gold → LangChain/Ollama → MLflow local")
    parser.add_argument("--snapshot", default=".cache/gold.jsonl")
    sub = parser.add_subparsers(dest="command", required=True)
    server = sub.add_parser("mlflow-local", help="Abrir o MLflow open source local")
    server.add_argument("--port", type=int, default=5001)
    server.add_argument("--data-dir", default=".cache/mlflow")
    api = sub.add_parser("api", help="Subir a API do front web (FastAPI, OpenAPI em /docs)")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8000)
    sub.add_parser("sync-gold", help="Ler a Gold com OAuth e SQL Warehouse")
    ask = sub.add_parser("ask")
    ask.add_argument("query")
    ask.add_argument("--niche")
    ask.add_argument("--backend", choices=["bm25", "dense"], default=None)
    ask.add_argument("--judge", action="store_true", help="Mostrar as notas do juiz")
    syn = sub.add_parser("synthesize", help="Agente de evidências: síntese de um tema")
    syn.add_argument("topic")
    syn.add_argument("--niche")
    syn.add_argument("--judge", action="store_true", help="Notas do juiz para a síntese")
    ad = sub.add_parser("adapt", help="Agente de comunicação: adaptar ao público")
    source = ad.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Texto a adaptar")
    source.add_argument("--file", help="Arquivo .txt com o texto")
    source.add_argument("--topic", help="Tema: evidências da Gold → texto adaptado")
    ad.add_argument("--audience", choices=list(AUDIENCES), default="leigo")
    ad.add_argument("--context", choices=list(CONTEXTS), default="palestra")
    ad.add_argument("--minutes", type=float, default=3)
    ad.add_argument("--tone", choices=["neutro", "formal", "informal"], default="neutro")
    ad.add_argument("--niche", help="Nicho para a busca (com --topic)")
    ad.add_argument("--judge", action="store_true", help="Notas do juiz para a adaptação")
    ev = sub.add_parser("evaluate", help="Avaliar e registrar no MLflow local")
    ev.add_argument("--dataset", default="data/evaluation/questions.jsonl")
    ev.add_argument("--backend", choices=["bm25", "dense"], default=None)
    ev.add_argument("--k", type=int, default=None)
    ev.add_argument("--generate", action="store_true", help="Gerar respostas com o Qwen")
    ev.add_argument("--judge", action="store_true", help="Notas de qualidade (requer --generate)")
    ev.add_argument("--limit", type=int)
    args = parser.parse_args()

    if args.command == "mlflow-local":
        if not 1 <= args.port <= 65535:
            parser.error("Porta inválida")
        if port_in_use(args.port):
            parser.error(
                f"A porta {args.port} já está em uso (no macOS a 5000 é do AirPlay). "
                "Use --port com outra porta e ajuste MLFLOW_TRACKING_URI."
            )
        folder = Path(args.data_dir).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        print(f"MLflow open source em http://127.0.0.1:{args.port}")
        command = [
            sys.executable,
            "-m",
            "mlflow",
            "server",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
            "--backend-store-uri",
            "sqlite:///" + str(folder / "mlflow.db"),
            "--serve-artifacts",
            "--artifacts-destination",
            str(folder / "artifacts"),
        ]
        raise SystemExit(subprocess.call(command))

    if args.command == "api":
        serve_api(args.host, args.port)
        return

    settings = Settings.from_env()
    if getattr(args, "backend", None):
        settings = replace(settings, backend=args.backend)
    if getattr(args, "k", None) is not None:
        settings = replace(settings, top_k=args.k)
    from rag_cognus.gold import load_from_databricks, load_snapshot, save_snapshot

    if args.command == "sync-gold":
        docs = load_from_databricks(settings)
        print(json.dumps(save_snapshot(docs, args.snapshot, settings.gold_view), indent=2))
        return

    from rag_cognus.evaluation import configure_tracking, evaluate, load_cases
    from rag_cognus.judges import make_judge
    from rag_cognus.retrieval import GoldRetriever

    configure_tracking(settings)
    if args.command == "adapt" and not args.topic:
        text = args.text if args.text is not None else Path(args.file).read_text()
        run_agents(args, settings, None, text)
        return
    retriever = GoldRetriever(load_snapshot(args.snapshot), settings)
    if args.command in {"synthesize", "adapt"}:
        run_agents(args, settings, retriever)
        return
    if args.command == "ask":
        from rag_cognus.chain import RagPipeline
        from rag_cognus.judges import as_dict, judge_response

        result = RagPipeline(retriever, settings).predict(args.query, args.niche)
        if args.judge:
            result["scores"] = as_dict(judge_response(make_judge(settings), args.query, result))
        result.pop("retrieved_context", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.judge and not args.generate:
        parser.error("--judge avalia respostas; use junto com --generate")
    cases = load_cases(args.dataset)
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit deve ser positivo")
        cases = cases[: args.limit]
    pipeline = None
    if args.generate:
        from rag_cognus.chain import RagPipeline

        pipeline = RagPipeline(retriever, settings)
    judge = make_judge(settings) if args.judge else None
    summary = evaluate(cases, retriever, settings, pipeline, judge)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nVeja no MLflow: {settings.tracking_uri}")
    if summary["metrics"].get("error/mean"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
