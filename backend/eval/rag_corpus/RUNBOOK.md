# ShadowCast Runbook

## Service Summary
- App: ShadowCast backend + static frontend assets
- Default URL: `http://127.0.0.1:8000` (override with `HOST` / `PORT`)
- Primary command: `python3 backend/app.py`

## Startup
1. Activate venv (canonical):
   - `source .venv/bin/activate`
   - Legacy alias: `venv/` is acceptable if that is your local env
2. Start server:
   - `python3 backend/app.py`
3. Open:
   - `http://127.0.0.1:8000`

## Health Checks
- Import/runtime checks:
  - `python3 -c "import fastapi, moviepy, PIL"`
- HTTP health:
  - `curl -fsS http://127.0.0.1:8000/api/health >/dev/null`
- Readiness (ffmpeg, ffprobe, LLM, TTS quality):
  - `curl -fsS http://127.0.0.1:8000/api/readiness`

## TTS and captions
- Shorts burn-in captions require `use_tts=true`.
- Quality providers: Kokoro, Piper, OpenAI. gTTS is smoke-only.
- UI auto-enables TTS when a quality provider is ready; API defaults prefer TTS on unless `SHADOWCAST_TTS_DEFAULT=0`.
- Live publish soft-blocks gTTS-only unless `ALLOW_GTTS_PUBLISH=1`.

## Playwright E2E

Two tiers against the real FastAPI + SPA (`http://127.0.0.1:8000`). Playwright starts uvicorn via `webServer` when nothing is already listening.

Prerequisites (shared):
- Root `.venv` with backend deps (`uvicorn`), or `python -m uvicorn` on PATH
- `npm install` at repo root
- `npx playwright install chromium`

### Tier 1 — mocked (default, CI)

```bash
npm run e2e
```

### Tier 2 — live generate (opt-in)

```bash
SHADOWCAST_E2E_LIVE=1 npm run e2e:live
```

Expect 5–15+ minutes. Do not run in CI.

## Daily Operations
- Process job creation via UI or Mission Control.
- Confirm generated files under `backend/output/` (or configured output).
- Prefer quality TTS + product `image_url` for postable assets (see `docs/SOCIAL_READINESS.md`).
- Monitor terminal logs for render or provider errors.

## Shutdown
- Stop server terminal (`Ctrl+C`) or kill the background PID if started with `nohup`.

## Common Failures

- `ffmpeg` / `ffprobe` missing: install FFmpeg package.
- Provider errors: verify local Ollama/service availability or API keys in local env.
- Silent Shorts: enable TTS so captions and VO render.
- gTTS publish blocked: install Kokoro/Piper/OpenAI TTS or set `ALLOW_GTTS_PUBLISH=1` for emergencies only.

## Style matrix / claim audit

From repo root:

```bash
.venv/bin/python -m pytest tests/test_content_styles.py tests/test_script_postprocessor.py tests/test_style_matrix.py tests/test_audio_options.py -q
.venv/bin/python backend/video_claim_audit.py --output-dir backend/output --fail-on warn
```

## RAG eval gates

```bash
cd backend
../.venv/bin/python eval/run_corpus_rag_eval.py --min-precision 0.80
../.venv/bin/python eval/run_rag_eval.py --min-relevance 0.80
```

## Quality gates (CI mirror)

See `.github/workflows/quality-gates.yml` and `scripts/quality/`.
