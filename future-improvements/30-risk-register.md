# Risk Register (Future Rewrite)

## Scoring

- **Likelihood:** Low / Medium / High
- **Impact:** Low / Medium / High
- **Priority:** Highest first based on combined risk

## R1 — Pipeline parity drift

- **Likelihood:** Medium
- **Impact:** High
- **Risk:** Stage isolation changes output behavior (script pacing, timing, assembly order).
- **Mitigation:** Snapshot parity fixtures + phase gates before rollout.
- **Owner:** Backend

## R2 — Retry duplication and artifact corruption

- **Likelihood:** Medium
- **Impact:** High
- **Risk:** Retries regenerate artifacts inconsistently or overwrite valid outputs.
- **Mitigation:** Idempotent stage contracts, deterministic naming, existence/hash checks.
- **Owner:** Backend

## R3 — Observability gaps during migration

- **Likelihood:** Medium
- **Impact:** Medium
- **Risk:** Failures become harder to diagnose if stage telemetry is incomplete.
- **Mitigation:** Require per-stage status, error type, and timestamps before each phase promotion.
- **Owner:** Backend

## R4 — Hidden operational complexity

- **Likelihood:** Medium
- **Impact:** Medium
- **Risk:** Queue/worker infra adds maintenance burden that outweighs throughput gain.
- **Mitigation:** Defer queue adoption until trigger thresholds are met; keep in-process fallback path.
- **Owner:** Product + Backend

## R5 — API compatibility regressions

- **Likelihood:** Low
- **Impact:** High
- **Risk:** Frontend integration breaks if status/results/download semantics drift.
- **Mitigation:** Lock API contract tests for `/api/status`, `/api/results`, `/api/download`.
- **Owner:** Backend

## R6 — Migration half-state trap

- **Likelihood:** Medium
- **Impact:** High
- **Risk:** Repo gets stuck between architectures with duplicated logic and unclear ownership.
- **Mitigation:** Phase completion checklist, explicit cutover points, and removal plan for deprecated path.
- **Owner:** Tech Lead

## R7 — Rewrite starts too early

- **Likelihood:** Medium
- **Impact:** Medium
- **Risk:** Team spends effort on architecture before rewrite-lite ROI is harvested.
- **Mitigation:** Enforce trigger criteria from `00-full-rewrite-summary.md`; prioritize surgical improvements first.
- **Owner:** Product

## Current Recommendation

Maintain rewrite-lite focus now. Re-evaluate full rewrite only when trigger criteria are met and measured pain justifies system complexity.
