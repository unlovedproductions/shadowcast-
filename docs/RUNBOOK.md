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
