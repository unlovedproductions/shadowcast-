# F2 — Stable prompt prefix dominates cloud cost/latency; local gains differ

**Status:** CONFIRMED for cloud (H2); PARTIAL for Ollama
**Sources:** 03, 14, 16, 17

## Thesis
Exact prefix match caching requires static system/rules first, dynamic product/RAG last. Min ~1024 tokens. Use prompt_cache_key; on newer OpenAI families use explicit breakpoints so dynamic suffixes don't poison cache writes.

## ShadowCast delta
Already done: system/user split, buyer rules in system, style RAG in user. Next: if using OpenAI, wire `prompt_cache_key` by style+format; keep retrieved chunks after stable instructions. Do not put timestamps/job IDs in system. RAG at front kills hit rate.

## Caveat
Low-QPS batch jobs may miss TTL (5–30m). Ollama local path: caching economics differ; focus on schema/eval, not provider cache.
