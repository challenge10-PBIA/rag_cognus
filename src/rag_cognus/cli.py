from __future__ import annotations

import argparse
import json
from dataclasses import replace

from dotenv import load_dotenv

from rag_cognus.config import Settings


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Cognus: Gold → LangChain/Ollama → MLflow")
    parser.add_argument("--snapshot", default=".cache/gold.jsonl")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sync-gold", help="Ler a Gold com OAuth e SQL Warehouse")
    ask = sub.add_parser("ask")
    ask.add_argument("query")
    ask.add_argument("--niche")
    ask.add_argument("--backend", choices=["bm25", "dense"], default=None)
    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("--dataset", default="data/evaluation/questions.jsonl")
    evaluate_parser.add_argument("--backend", choices=["bm25", "dense"], default=None)
    evaluate_parser.add_argument("--k", type=int, default=None)
    evaluate_parser.add_argument("--generate", action="store_true")
    evaluate_parser.add_argument("--limit", type=int)
    judge = sub.add_parser("judge")
    judge.add_argument("results")
    args = parser.parse_args()
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
    from rag_cognus.evaluation import (
        configure_tracking,
        evaluate,
        evaluate_groundedness,
        load_cases,
    )

    if args.command == "judge":
        print(evaluate_groundedness(args.results, settings))
        return
    configure_tracking(settings)
    from rag_cognus.retrieval import GoldRetriever

    docs = load_snapshot(args.snapshot)
    retriever = GoldRetriever(docs, settings)
    if args.command == "ask":
        from rag_cognus.chain import RagPipeline

        result = RagPipeline(retriever, settings).predict(args.query, args.niche)
        result.pop("retrieved_context", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        cases = load_cases(args.dataset)
        if args.limit is not None:
            if args.limit < 1:
                parser.error("--limit deve ser positivo")
            cases = cases[: args.limit]
        pipeline = None
        if args.generate:
            from rag_cognus.chain import RagPipeline

            pipeline = RagPipeline(retriever, settings)
        result = evaluate(cases, retriever, settings, pipeline)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["metrics"]["error_rate"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
