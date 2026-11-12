#!/usr/bin/env python3
"""Run style-rules corpus RAG eval and enforce precision@5 floor."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
BACKEND = EVAL.parent
sys.path.insert(0, str(BACKEND))

from rag_store import StyleCorpusStore

FIXTURES = EVAL / "fixtures"
CORPUS = EVAL / "rag_corpus"
DEFAULT_OUTPUT = EVAL / "artifacts" / "rag_eval.json"


def _load_queries(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("queries", [])


def _load_ground_truth(path: Path) -> dict[str, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v if isinstance(v, list) else [v] for k, v in data.items()}


def _reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for idx, doc_id in enumerate(retrieved):
        if doc_id in relevant:
            return 1.0 / (idx + 1)
    return 0.0


def _ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    retrieved_k = retrieved[:k]
    dcg = sum(1 / math.log2(i + 2) for i, doc in enumerate(retrieved_k) if doc in relevant)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_corpus(
    store: StyleCorpusStore,
    queries: list[dict],
    ground_truth: dict[str, list[str]],
    *,
    k_values: list[int] | None = None,
) -> dict:
    k_values = k_values or [3, 5, 10]
    max_k = max(k_values)
    query_results = []
    agg = {f"mean_precision@{k}": [] for k in k_values}
    agg.update({f"mean_recall@{k}": [] for k in k_values})
    agg.update({f"mean_ndcg@{k}": [] for k in k_values})
    reciprocal_ranks: list[float] = []

    for query_data in queries:
        query_id = query_data["id"]
        query_text = query_data["query"]
        relevant = set(ground_truth.get(query_id, []))
        if not relevant:
            continue

        results = store.retrieve_documents(query_text, top_k=max_k)
        retrieved_ids = [doc_id for doc_id, _ in results]
        metrics: dict[str, float] = {}

        for k in k_values:
            top_ids = retrieved_ids[:k]
            top = set(top_ids)
            hit = top & relevant
            precision = len(hit) / len(top) if top else 0.0
            recall = len(hit) / len(relevant) if relevant else 0.0
            metrics[f"precision@{k}"] = precision
            metrics[f"recall@{k}"] = recall
            metrics[f"ndcg@{k}"] = _ndcg_at_k(retrieved_ids, relevant, k)
            agg[f"mean_precision@{k}"].append(precision)
            agg[f"mean_recall@{k}"].append(recall)
            agg[f"mean_ndcg@{k}"].append(metrics[f"ndcg@{k}"])

        rr = _reciprocal_rank(retrieved_ids, relevant)
        metrics["reciprocal_rank"] = rr
        reciprocal_ranks.append(rr)

        query_results.append(
            {
                "query_id": query_id,
                "query": query_text,
                "relevant_count": len(relevant),
                "retrieved_count": len(retrieved_ids),
                "metrics": metrics,
                "retrieved_docs": results[:5],
                "relevant_docs": sorted(relevant),
            }
        )

    aggregate_metrics = {
        key: (sum(values) / len(values) if values else 0.0)
        for key, values in agg.items()
    }
    aggregate_metrics["mean_reciprocal_rank"] = (
        sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
    )

    p5 = aggregate_metrics.get("mean_precision@5", 0.0)
    r10 = aggregate_metrics.get("mean_recall@10", 0.0)
    summary = (
        f"Evaluation Summary ({len(query_results)} queries):\n"
        f"{'=' * 50}\n"
        f"Precision@5:  {p5:.3f} ({p5 * 100:.1f}%)\n"
        f"Recall@10:    {r10:.3f} ({r10 * 100:.1f}%)\n"
        f"MRR:          {aggregate_metrics.get('mean_reciprocal_rank', 0):.3f}\n"
    )

    return {
        "aggregate_metrics": aggregate_metrics,
        "query_results": query_results,
        "failure_analysis": {
            "poor_precision_count": sum(
                1 for q in query_results if q["metrics"].get("precision@5", 0) < 0.5
            ),
            "zero_results_count": sum(1 for q in query_results if q["retrieved_count"] == 0),
        },
        "evaluation_summary": summary,
        "recommendations": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Style-rules corpus RAG eval gate")
    parser.add_argument("--min-precision", type=float, default=0.80)
    parser.add_argument("--queries", default=str(FIXTURES / "rag_queries.json"))
    parser.add_argument("--ground-truth", default=str(FIXTURES / "rag_ground_truth.json"))
    parser.add_argument("--corpus", default=str(CORPUS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    queries = _load_queries(Path(args.queries))
    ground_truth = _load_ground_truth(Path(args.ground_truth))
    store = StyleCorpusStore(Path(args.corpus))
    report = evaluate_corpus(store, queries, ground_truth)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    p5 = float(report["aggregate_metrics"].get("mean_precision@5", 0))
    print(f"Corpus RAG precision@5: {p5:.3f} (min {args.min_precision:.2f})")
    if p5 < args.min_precision:
        print("Corpus RAG eval gate failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
