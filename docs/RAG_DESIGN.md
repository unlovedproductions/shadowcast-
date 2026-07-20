# RAG Design (ShadowCast)

Design-only spike for a future retrieval layer. Does **not** replace [`research_enrichment.py`](../backend/research_enrichment.py) (live Amazon/YouTube enrichment).

## Use case

Retrieve style guides, prompt rules, and runbook snippets during script generation so the LLM follows buyer-language bans, content-style constraints, and eval gates.

## Corpus (phase 6)

| Path | Role |
|------|------|
| `docs/*.md` | Architecture, runbook, recovery, style checklist |
| `backend/eval/AUDIT.md` | Prompt eval gates and buyer-language rules |

Copied to `backend/eval/rag_corpus/` for tooling.

## Chunking (`chunking_optimizer.py`)

- **Corpus:** 5 documents, ~11.6 KB total
- **Recommended strategy:** `sentence_based` (from `rag_pipeline_designer.py`; fixed-size char also evaluated in `backend/eval/artifacts/chunking.json`)
- **Sample config:** max 1000 chars, 1-sentence overlap

## Pipeline design (`rag_pipeline_designer.py`)

| Component | Recommendation | Notes |
|-----------|----------------|-------|
| Embeddings | `all-MiniLM-L6-v2` tier (verify current model availability) | Self-hosted, cost-sensitive |
| Vector store | pgvector | Fits low query volume (~50/day) |
| Retrieval | Hybrid BM25 + vector | Designer output in `backend/eval/artifacts/rag_design.json` |
| Reranking | Cross-encoder (optional phase 2) | Needed if precision stays below target |

**Cost figures in `rag_design.json` are estimates — verify live pricing before production.**

## Evaluation (`retrieval_evaluator.py`)

Fixtures:

- `backend/eval/fixtures/rag_queries.json` — 5 dev queries
- `backend/eval/fixtures/rag_ground_truth.json` — doc stem IDs matching corpus filenames

Latest run: `backend/eval/artifacts/rag_eval.json`

**Targets (production gate):** precision@5 ≥ 0.8, recall@10 ≥ 0.85

**Latest baseline (TF-IDF, 5-doc corpus):** precision@5 = 0.6, recall@10 = 0.8, MRR = 0.7 — below precision target; recall meets target.

1. Expand corpus with `mock_scripts.json` exemplars and `prompts.py` exports
2. Switch chunking per `chunking.json` recommendation
3. Add embedding + pgvector index (design already specifies stack)
4. Add cross-encoder reranking

## Integration point (future)

```
product_info + hook_types
    → retrieve(style_rules, buyer_bans, format_examples)
    → inject into script_generator system context
    → existing LLM + validators (unchanged)
```

Do not wire into `/api/generate` until eval targets pass on an expanded corpus.

## Commands

```bash
python3 scripts/quality/chunking_optimizer.py backend/eval/rag_corpus --extensions .md -o backend/eval/artifacts/chunking.json
python3 scripts/quality/rag_pipeline_designer.py backend/eval/fixtures/rag_requirements.json -o backend/eval/artifacts/rag_design.json
python3 scripts/quality/retrieval_evaluator.py backend/eval/fixtures/rag_queries.json backend/eval/rag_corpus backend/eval/fixtures/rag_ground_truth.json -o backend/eval/artifacts/rag_eval.json
```
