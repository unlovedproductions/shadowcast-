#!/usr/bin/env python3
"""Run product RAG evaluation fixtures and enforce relevance + groundedness floors."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
BACKEND = EVAL.parent
FIXTURES = EVAL / "fixtures"
BASELINES = EVAL / "baselines"

sys.path.insert(0, str(BACKEND))

from rag_store import ResearchStore


def _build_product_contexts() -> list[dict]:
    """Build retrieval contexts from fixture product research snippets."""
    store = ResearchStore(FIXTURES / "_rag_product_fixture", embed_base_url="")
    store._add_chunks(
        ["SoundCore Space A40 complaints often mention ANC cutouts on trains and case scratches after daily carry."],
        "amazon_review_negative",
        {"type": "review"},
    )
    store._add_chunks(
        ["SoundCore Space A40 praises highlight battery life, strong ANC performance, and good value for the price."],
        "amazon_review_positive",
        {"type": "review"},
    )
    store._add_chunks(
        ["Recommended YouTube tags: wireless earbuds, ANC earbuds, budget review, commuter earbuds, honest review."],
        "youtube_tags",
        {"type": "tags"},
    )

    contexts: list[dict] = []
    mapping = {
        "q_complaints": "SoundCore Space A40 common complaints and limitations",
        "q_praises": "SoundCore Space A40 praised features and strengths",
        "q_tags": "YouTube tags wireless earbuds ANC earbuds budget review",
    }
    for question_id, query in mapping.items():
        hits = store.retrieve(query, top_k=1, rerank=True)
        text = hits[0]["text"] if hits else ""
        contexts.append({"question_id": question_id, "content": text})
    return contexts


def main() -> int:
    parser = argparse.ArgumentParser(description="ShadowCast product RAG eval gate")
    parser.add_argument("--min-relevance", type=float, default=0.80)
    parser.add_argument("--min-groundedness", type=float, default=0.85)
    parser.add_argument("--output", default=str(EVAL / "artifacts" / "rag_product_eval.json"))
    parser.add_argument("--use-store-contexts", action="store_true", default=True)
    args = parser.parse_args()

    questions = FIXTURES / "rag_questions.json"
    contexts_path = FIXTURES / "rag_contexts.json"
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    eval_contexts = FIXTURES / "_rag_eval_contexts.json"
    if args.use_store_contexts:
        eval_contexts.write_text(json.dumps(_build_product_contexts(), indent=2), encoding="utf-8")
        contexts_arg = str(eval_contexts)
    else:
        contexts_arg = str(contexts_path)

    cmd = [
        sys.executable,
        str(EVAL / "rag_evaluator.py"),
        "--contexts",
        contexts_arg,
        "--questions",
        str(questions),
        "--json",
        "--output",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr or proc.stdout, file=sys.stderr)
        return proc.returncode

    report = json.loads(out.read_text(encoding="utf-8"))
    baseline_path = BASELINES / "rag_product_baseline.json"
    baseline_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    relevance = float(report.get("avg_context_relevance", 0))
    groundedness = float(report.get("avg_groundedness", 0))
    print(f"RAG relevance: {relevance:.3f} (min {args.min_relevance:.2f})")
    print(f"RAG groundedness: {groundedness:.3f} (min {args.min_groundedness:.2f})")

    failed = False
    if relevance < args.min_relevance:
        print("RAG relevance gate failed", file=sys.stderr)
        failed = True
    if groundedness < args.min_groundedness:
        print("RAG groundedness gate failed", file=sys.stderr)
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
