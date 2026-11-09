"""Suite reprodutível: recuperação, geração e juiz opcional no MLflow local."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import httpx
from dotenv import load_dotenv

from rag_cognus.chain import RagPipeline
from rag_cognus.config import Settings
from rag_cognus.evaluation import evaluate, evaluate_groundedness, load_cases
from rag_cognus.gold import load_snapshot
from rag_cognus.retrieval import GoldRetriever


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", default="http://127.0.0.1:5000")
    parser.add_argument("--generate-limit", type=int, default=2)
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--backend", choices=["bm25", "dense"], default="bm25")
    args = parser.parse_args()
    if args.generate_limit < 0:
        parser.error("--generate-limit deve ser zero ou positivo")
    if args.judge and args.generate_limit == 0:
        parser.error("--judge exige --generate-limit maior que zero")
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    try:
        httpx.get(args.uri.rstrip("/") + "/health", timeout=5).raise_for_status()
    except httpx.HTTPError as exc:
        raise SystemExit("Inicie primeiro: rag-cognus mlflow-local") from exc
    settings = replace(
        Settings.from_env(), tracking_uri=args.uri, backend=args.backend, experiment="rag-cognus"
    )
    docs = load_snapshot(root / ".cache/gold.jsonl")
    cases = load_cases(root / "data/evaluation/questions.jsonl")
    output = root / "outputs"
    runs = []
    for k in (3, 5):
        config = replace(settings, top_k=k)
        retriever = GoldRetriever(docs, config)
        runs.append(
            evaluate(
                cases,
                retriever,
                config,
                output_dir=output,
                run_name=f"local-retrieval-{args.backend}-k{k}",
            )
        )
    generated = None
    if args.generate_limit:
        config = replace(settings, top_k=5)
        retriever = GoldRetriever(docs, config)
        generated = evaluate(
            cases[: args.generate_limit],
            retriever,
            config,
            pipeline=RagPipeline(retriever, config),
            output_dir=output,
            run_name=f"local-rag-qwen-{args.backend}",
        )
        runs.append(generated)
    report = {"tracking_uri": args.uri, "runs": runs}
    if args.judge:
        if generated is None:
            parser.error("--judge exige geração; use --generate-limit maior que zero")
        report["judge_run_id"] = evaluate_groundedness(
            output / (generated["run_id"] + ".json"), settings
        )
    (output / "local_eval_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if any(run["metrics"]["error_rate"] for run in runs):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
