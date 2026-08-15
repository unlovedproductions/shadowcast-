# 27 — Celery+Redis when unneeded (practitioner)

- **URL:** https://tomodahinata.com/en/blog/celery-redis-production-async-task-queue-guide
- **Type:** practitioner
- **Credibility:** 3 | **Recency:** 4 | **Bias:** low

## Verbatim quotes

> Celery is powerful but comes with operational cost (worker, broker, monitoring).

> Light processing that completes within the request… Celery unneeded. Synchronous is enough. A queue is just added complexity

## Relevance

**H8:** Aligns with ShadowCast deferred rewrite — fail-fast checkpoints first, not Redis.
