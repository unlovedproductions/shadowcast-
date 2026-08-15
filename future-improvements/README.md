# Future Improvements

Future rewrite planning is documented here for later execution. Rewrite-lite work continues in the live codebase first.

## Document Index

1. `00-full-rewrite-summary.md`
   - Why the full rewrite is deferred and what triggers it.
2. `10-target-architecture.md`
   - Future state architecture, stage contracts, and non-goals.
3. `20-migration-plan.md`
   - Phased migration sequence, entry/exit criteria, and rollback points.
4. `30-risk-register.md`
   - Top risks, impact/likelihood, mitigation, and owners.

PDF siblings are optional exports — markdown is canonical.

## Constraints

- No immediate architecture rewrite.
- Migration Phases 0–4 in `20-migration-plan.md` remain deferred until rewrite trigger criteria are met.
- No queue stack commitment yet (Redis/Celery deferred).
- Preserve current API contract during future migration.

## Rewrite-lite already landed

- Job persistence extracted to `backend/job_store.py`.
- Optional parallel batch workers via `SHADOWCAST_BATCH_WORKERS`.
- TTS-first timing, loudnorm/ducking, Shorts captions remain in-process (assemble pipeline).
