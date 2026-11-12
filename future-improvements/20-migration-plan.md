# Migration Plan (Future Rewrite)

## Objective

Move from monolithic in-process orchestration to staged execution with minimal downtime, bounded risk, and rollback safety at every phase.

## Phase 0 — Preconditions

- Freeze non-critical architecture changes.
- Define canonical artifact naming and stage checkpoint schema.
- Add baseline telemetry for current pipeline latency/failure.
- Confirm parity test fixtures for script/audio/video outputs.

**Exit criteria**
- Baseline metrics captured.
- Parity fixtures available for at least 3 representative products.

## Phase 1 — Introduce Stage Contracts In-Process

- Keep current runtime model.
- Refactor orchestration boundaries to explicit stage interfaces without changing endpoint behavior.
- Persist stage-level checkpoints in existing job state.

**Exit criteria**
- Existing jobs complete with no API contract changes.
- Stage checkpoints visible and recoverable in current process.

## Phase 2 — Isolate Script + Audio Execution Paths

- Route script and audio through dispatcher semantics (still same deployment boundary initially).
- Ensure retries are stage-scoped.
- Validate artifact idempotency under repeated runs.

**Exit criteria**
- Script/audio retries do not force full pipeline reruns.
- No regression in package output structure.

## Phase 3 — Isolate Video + Assemble Execution Paths

- Move video/assemble into the same stage contract model.
- Enforce strict input/output checks before stage transition.
- Add explicit failure reasons per stage for UI/status debugging.

**Exit criteria**
- End-to-end runs recover from single-stage failures.
- Final artifacts remain identical or intentionally improved.

## Phase 4 — Optional Queue Backend Adoption

- Evaluate queue backend only if trigger criteria are active.
- Start with one stage path, then expand after observed stability.

**Exit criteria**
- Throughput gain and recovery improvements are measurable.
- Operational complexity remains acceptable.

## Rollback Strategy

- Roll back one phase at a time; never jump multiple phases backward in a single move.
- Keep old execution path behind a runtime flag until each phase is stable.
- Preserve artifact compatibility to avoid invalidating completed jobs.

## Acceptance Gates

- No API breakage for frontend calls.
- No increase in failed job percentage relative to baseline.
- Mean recovery time improves or remains neutral during each phase.
- On-call/debug burden does not increase materially.
