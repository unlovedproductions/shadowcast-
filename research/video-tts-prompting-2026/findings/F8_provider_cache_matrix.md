# F8 — Provider cache matrix for script volume

**Status:** CONFIRMED extension of H2
**Sources:** 03, 27, 28, 29, 30

## Thesis
OpenAI needs prompt_cache_key (+ explicit breakpoints on GPT-5.6+). Anthropic needs cache_control on last static block (not on product block). Gemini: implicit prefix or explicit cachedContents for large static RAG. Ollama: keep_alive=-1 for batch; exact prefix match; speculation helps decode not prefill.

## ShadowCast
Ollama path: keep_alive for batch eval. Cloud path: category-bucketed style RAG in cached prefix, product facts last. Unified schema — schema churn kills OpenAI cache.
