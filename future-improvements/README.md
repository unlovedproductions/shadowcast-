# Future Improvements

Future rewrite planning is documented here for later execution. Rewrite-lite work continues in the live codebase first.

## Document Index

1. `00-full-rewrite-summary.md` / `00-full-rewrite-summary.pdf`
   - Why the full rewrite is deferred and what triggers it.
2. `10-target-architecture.md` / `10-target-architecture.pdf`
   - Future state architecture, stage contracts, and non-goals.
3. `20-migration-plan.md` / `20-migration-plan.pdf`
   - Phased migration sequence, entry/exit criteria, and rollback points.
4. `30-risk-register.md` / `30-risk-register.pdf`
   - Top risks, impact/likelihood, mitigation, and owners.

## Constraints

- No immediate architecture rewrite.
- No queue stack commitment yet (Redis/Celery deferred).
- Preserve current API contract during future migration.
