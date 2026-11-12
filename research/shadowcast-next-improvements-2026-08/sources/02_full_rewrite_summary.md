# 02 — Full Rewrite Summary Deferred (local primary)

- **URL:** file:///home/unloved/shadowcast-/future-improvements/00-full-rewrite-summary.md
- **Date:** project doc (current)
- **Type:** primary (project)
- **Credibility:** 5 | **Recency:** 4 | **Bias:** low

## Verbatim quotes

> Stage boundaries are not independently recoverable.

> Full rewrite is intentionally deferred.

> Begin rewrite planning-to-build transition only when at least two conditions persist: Concurrency pressure… Partial failures require frequent manual repair… Stage-specific bottlenecks… Recovery time… Product scope expansion…

> Avoid introducing queue infrastructure until trigger criteria are met.

## Relevance

Supports **H8** nuance: fail-fast/stage recovery matters, but full DAG/queue rewrite is deferred until triggers fire — incremental fail-fast inside current architecture preferred.
