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
