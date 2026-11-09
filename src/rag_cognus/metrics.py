from __future__ import annotations

import json


def retrieval_metrics(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> dict:
    """Referências devem ser revisadas; duplicatas não recebem crédito adicional."""
    if k < 1 or not relevant_ids:
        raise ValueError("k positivo e referências não vazias são obrigatórios.")
    if len(retrieved_ids) != len(set(retrieved_ids)):
        raise ValueError("Resultado contém IDs duplicados.")
    ranked = retrieved_ids[:k]
    relevant = set(relevant_ids)
    found = relevant.intersection(ranked)
    first = next((i for i, cid in enumerate(ranked, 1) if cid in relevant), None)
    return {
        "precision_at_k": len(found) / k,
        "recall_at_k": len(found) / len(relevant),
        "hit_at_k": float(bool(found)),
        "mrr_at_k": 1 / first if first else 0.0,
    }


def score_case(case: dict, output: dict, k: int) -> dict:
    expected = case.get("expectations", {})
    human = expected.get("label_status") == "human_verified"
    metrics = {}
    ids = output.get("retrieved_chunk_ids", [])
    if human and expected.get("relevant_chunk_ids"):
        metrics.update(retrieval_metrics(ids, expected["relevant_chunk_ids"], k))
    if expected.get("expected_niche"):
        hits = output.get("retrieved_context", [])
        n = sum(
            expected["expected_niche"] in json.loads(h["metadata"].get("nichos_json", "[]"))
            for h in hits
        )
        # Proxy de consistência com os rótulos da própria Gold; NÃO relevância semântica.
        metrics["niche_metadata_precision_proxy"] = n / len(hits) if hits else 0.0
    if "response" in output:
        cited = output.get("cited_chunk_ids", [])
        metrics["citation_integrity"] = float(
            set(cited).issubset(ids) and (output.get("abstained", False) or bool(cited))
        )
        if human and isinstance(expected.get("should_abstain"), bool):
            metrics["abstention_agreement"] = float(
                output["abstained"] == expected["should_abstain"]
            )
    return metrics
