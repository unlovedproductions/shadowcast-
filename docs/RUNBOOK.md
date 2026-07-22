# ShadowCast Runbook

## Service Summary
- App: ShadowCast backend + static frontend assets
- Default URL: `http://localhost:8000`
- Primary command: `python3 backend/app.py`

## Startup
1. Activate venv:
   - `source venv/bin/activate`
2. Start server:
   - `python3 backend/app.py`
3. Open:
   - `http://localhost:8000`

## Health Checks
- Import/runtime checks:
  - `python3 -c "import fastapi, moviepy, PIL"`
- HTTP health:
  - `curl -fsS http://localhost:8000/api/health >/dev/null`

## Daily Operations
- Process job creation via UI or Mission Control.
- Confirm generated files are written to expected output locations.
- Monitor terminal logs for render or provider errors.

## Shutdown
- Stop server terminal (`Ctrl+C`) or kill the background PID if started with `nohup`.

## Common Failures

- `ffmpeg` missing: install FFmpeg package.
- Provider errors: verify local Ollama/service availability or API keys in local env.
- Render failures: validate product payload and available disk space.

## Prompt Eval (LLM)

Static analysis and validator dry-run (no LLM required):

```bash
cd backend
python3 eval/export_snapshots.py
python3 eval/prompt_optimizer.py eval/snapshots/script_short_honest_review.txt --analyze --model qwen2.5
python3 eval/eval_runner.py --output eval/baselines/eval_baseline.json
pytest ../tests/test_prompt_eval.py -q
```

Live LLM eval (requires Ollama or configured provider):

```bash
cd backend
LLM_EVAL=1 pytest ../tests/test_prompt_eval.py -m llm -q
python3 eval/eval_runner.py --live --filter hr_short,hr_long --output eval_results.json
```

See `backend/eval/AUDIT.md` for baseline metrics and iteration gates.

Corpus and product RAG gates:

```bash
cd backend
python3 eval/run_corpus_rag_eval.py --min-precision 0.80
python3 eval/run_rag_eval.py --min-relevance 0.80
```

Style-rules doc retrieval during generation is on by default; set `STYLE_RULES_RAG=0` to disable injection into script prompts.

## Quality Gates

Local checks (from repo root):

```bash
cd backend && .venv/bin/python export_openapi.py -o ../docs/openapi.json
python3 scripts/quality/api_linter.py docs/openapi.json
python3 scripts/quality/api_scorecard.py docs/openapi.json --min-grade B
python3 scripts/quality/breaking_change_detector.py docs/openapi.baseline.json docs/openapi.json
cd backend && .venv/bin/pytest ../tests/test_api_routes.py ../tests/ -q -m "not llm"
python3 scripts/quality/ship_gate_scanner.py backend --no-interactive
python3 scripts/quality/ship_gate_scanner.py frontend --no-interactive
```

CI runs the same gates via `.github/workflows/quality-gates.yml`.

OpenAPI policy: unversioned `/api/*` URLs are intentional for this internal UI-backed API. Breaking changes require updating `docs/openapi.baseline.json` on semver bumps.

## Rollback (Vercel)

1. Identify last good deploy in the Vercel dashboard.
2. Promote that deploy to production (instant rollback).
3. If API contract changed, revert `docs/openapi.baseline.json` in git and redeploy.
4. For bad releases with DB/file side effects, disable feature flags first; ShadowCast is file-based for job output — no destructive DB migrations to roll back.

