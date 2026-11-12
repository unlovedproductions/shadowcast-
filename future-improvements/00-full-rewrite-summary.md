# Full Rewrite Summary (Deferred)

## Purpose

Define the future architecture rewrite direction without executing it now. This keeps implementation focused on low-risk rewrite-lite improvements while preserving a clear path when scale pressure makes a rewrite unavoidable.

## Current State Snapshot

- Core orchestration is centralized in `backend/app.py`.
- Generation currently executes as long in-process flows (`_run_single_product`, `_run_generation`, `_run_batch_generation`).
- Rendering and assembly concerns are tightly coupled in `backend/video_renderer.py`.
- Job artifacts and basic durability exist, but stage boundaries are not independently recoverable.
- Operational scaling is mostly vertical (single-process pressure grows before stage-level isolation can help).

## Rewrite Outcome (Future State)

Shift to a staged, durable pipeline with explicit contracts:

- Script stage
- Audio stage
- Video stage
- Assemble stage

Each stage runs idempotently, reports status independently, and can retry without replaying the full pipeline.

## Decision

Full rewrite is intentionally deferred.

Current priority is rewrite-lite: trust fixes, conversion polish, prompt/context quality, and reliability hardening inside the existing architecture.

## Rewrite Trigger Criteria

Begin rewrite planning-to-build transition only when at least two conditions persist:

- Concurrency pressure repeatedly causes SLA misses.
- Partial failures require frequent manual repair or reruns.
- Stage-specific bottlenecks (LLM/TTS/render) need independent scaling.
- Recovery time from failed jobs is materially above acceptable thresholds.
- Product scope expansion requires more parallel throughput than in-process orchestration can safely provide.

## Guardrails Until Rewrite

- Keep API compatibility stable (`/api/status`, `/api/results`, `/api/download`).
- Avoid introducing queue infrastructure until trigger criteria are met.
- Prefer surgical improvements over structural churn.
