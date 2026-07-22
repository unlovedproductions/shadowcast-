# ShadowCast Prompt Baseline Audit

Generated after centralizing prompts in `backend/prompts.py` and applying eval-gated optimizations (trimmed hooks, system/user split, tightened JSON schemas).

Model token estimate family: `qwen2.5` (4.0 chars/token).

## Token and Score Summary

| Snapshot | Tokens | Clarity | Structure | Issues |
|----------|--------|---------|-----------|--------|
| script_short_honest_review | 1,120 | 70 | 90 | 5 redundancy |
| script_long_honest_review | 1,290 | 65 | 90 | 6 (1 ambiguity, 5 redundancy) |
| script_short_vs_battle | 1,110 | 31 | 90 | 18 redundancy (product data overlap) |
| youtube_assets_long | 761 | 71 | 65 | 8 redundancy |

## Findings

### Addressed in this iteration

1. **Verbose hook examples removed** — `HOOK_DESCRIPTIONS` trimmed from multi-sentence examples to one-line definitions (~300–400 token savings vs prior inline examples).
2. **Stable prefix moved to system prompt** — research framing and buyer rules now live in `SCRIPT_SYSTEM_PROMPT` / `YOUTUBE_ASSETS_SYSTEM_PROMPT` for cache-friendly layout.
3. **JSON schema tightened** — angle-bracket placeholders replaced with explicit type names (`number`, `string`, `boolean`).
4. **YouTube SEO rules deduplicated** — buyer SEO + pinned comment strategy moved to system; user prompt carries product/script context only.

### Remaining (acceptable or fixture-driven)

1. **Product data redundancy in vs_battle** — competitors and price comparison repeat in comparison block; intentional for layout segment accuracy. Clarity score on vs_battle snapshot is low due to analyzer flagging repeated product names, not instruction ambiguity.
2. **Long-form "The Good" ambiguity flag** — static analyzer flags subjective "Good"; acceptable for chapter naming.
3. **YouTube user prompt link repetition** — product link appears in schema footer and closing instruction; minor, keeps grounding explicit for local models.

### JSON enforcement stack

| Layer | OpenAI | Ollama/local |
|-------|--------|--------------|
| System | JSON-only rule | JSON-only rule |
| User | OUTPUT JSON SCHEMA | OUTPUT JSON SCHEMA |
| API | `response_format: json_object` | `_strip_json_instruction` suffix in `llm_client` |

OpenAI path avoids redundant user suffix; local path keeps schema + suffix (required for Qwen/Ollama).

## Recommendations (future, eval-gated)

| Priority | Change | When |
|----------|--------|------|
| 1 | Run `--live` eval against Ollama before prompt edits | **Done** — 16/16 live baseline (`eval/baselines/eval_live_baseline.json`) |
| 2 | Add contrastive few-shot only if live eval shows JSON parse cluster failures | After live baseline |
| 3 | Deduplicate comparison block vs product fields for vs_battle only | If token budget tightens |

## Commands

```bash
cd backend
python3 eval/export_snapshots.py
python3 eval/prompt_optimizer.py eval/snapshots/script_short_honest_review.txt --analyze --json --model qwen2.5 --output eval/baselines/script_short_honest_review.json
python3 eval/eval_runner.py --output eval/baselines/eval_baseline.json
python3 eval/eval_runner.py --live --filter hr_short,hr_long --output eval_results.json
python3 eval/eval_runner.py --compare eval_results.json eval/baselines/eval_baseline.json
```

## Live eval baseline

Dry-run validator baseline: **16/16 passed** (`eval/baselines/eval_baseline.json`).

Live LLM baseline: **16/16 passed**, `pending_live: 0` (`eval/baselines/eval_live_baseline.json`).

Re-run smoke subset before prompt-affecting changes:

```bash
cd backend
LLM_EVAL=1 python3 eval/eval_runner.py --live --filter hr_short,vs_short,elim_short --output eval_results.json
python3 eval/eval_runner.py --compare eval_results.json eval/baselines/eval_live_baseline.json
```

## Style-rules RAG

Style corpus retrieval is **enabled by default** during script generation (`style_rules_retrieval.py` → `_style_rules_context` in user prompt). Disable with `STYLE_RULES_RAG=0`. See [`docs/RAG_DESIGN.md`](../../docs/RAG_DESIGN.md).

## RAG eval gates

```bash
cd backend
python3 eval/run_corpus_rag_eval.py --min-precision 0.80
python3 eval/run_rag_eval.py --min-relevance 0.80
```
