# ShadowCast Runbook

## Service Summary
- App: ShadowCast backend + static frontend assets
- Default URL: `http://127.0.0.1:8000` (override with `HOST` / `PORT`)
- Primary command: `python3 backend/app.py`

## Startup
1. Activate venv (canonical):
   - `source .venv/bin/activate`
   - Legacy alias: `venv/` is acceptable if that is your local env
2. (Recommended) fetch operator media once per machine:
   - `./scripts/fetch_operator_media.sh`
3. Start server:
   - `python3 backend/app.py`
4. Open:
   - `http://127.0.0.1:8000`

## Health Checks
- Import/runtime checks:
  - `python3 -c "import fastapi, moviepy, PIL"`
- HTTP health:
  - `curl -fsS http://127.0.0.1:8000/api/health >/dev/null`
- Readiness (ffmpeg, ffprobe, LLM, TTS quality, music/B-roll completeness):
  - `curl -fsS http://127.0.0.1:8000/api/readiness`
- Media library inventory (moods/tags, missing beds):
  - `curl -fsS 'http://127.0.0.1:8000/api/media-library'`
  - Optional search: `curl -fsS 'http://127.0.0.1:8000/api/media-library?q=mood'`

## TTS and captions
- Shorts burn-in captions require `use_tts=true`.
- Quality providers: Kokoro (local ONNX under `backend/assets/kokoro/`), Piper, OpenAI. gTTS is smoke-only.
- UI auto-enables TTS when a quality provider is ready; API defaults prefer TTS on unless `SHADOWCAST_TTS_DEFAULT=0`.
- Pronunciation lexicon: `SHADOWCAST_TTS_PRONUNCIATIONS`; seam polish via `SHADOWCAST_TTS_CROSSFADE` / `SHADOWCAST_TTS_INTER_SEGMENT_PAUSE`.
- Live publish soft-blocks gTTS-only unless `ALLOW_GTTS_PUBLISH=1`.
- Optional karaoke align: `SHADOWCAST_WHISPERX_ALIGN=1` (+ optional `whisperx` install).
- Optional long-form B-roll pads: drop clips in `backend/assets/broll/` or set `SHADOWCAST_BROLL=1`.

## Operator media and encode
- Music beds: `backend/assets/music/{mood}.wav` (`chill`, `energetic`, `dramatic`, `minimal`). See `backend/assets/music/ATTRIBUTION.md`.
- B-roll tags: `pad`, `default`, `pros`, `cons`, `verdict`, `comparison` under `backend/assets/broll/`.
- Preferred fetch: `./scripts/fetch_operator_media.sh`.
- Live publish hard-blocks when no music beds are present unless `ALLOW_SYNTH_MUSIC_PUBLISH=1`.
- Optional NVENC: `SHADOWCAST_FFMPEG_CODEC=auto` (default) uses `h264_nvenc` when ffmpeg reports it; force `libx264` or `h264_nvenc` as needed. Preset via `SHADOWCAST_VIDEO_PRESET`.

## Observability
- Optional Sentry: set `SENTRY_DSN` (API) and/or `SENTRY_FRONTEND_DSN` (SPA loader). `SENTRY_ENVIRONMENT` tags events. Health/readiness traces are dropped.

## Publish dry-run vs live
- UI **Dry Run** and API `dry_run: true` never upload — publishers return synthetic success payloads.
- Use dry-run first for YouTube / Meta / TikTok / **Rumble**.
- Rumble live publish needs browser login cookies via OAuth/Rumble connect; Playwright selectors are multi-fallback (title/desc/file/submit). If upload DOM changes, reconnect session and check `rumble_publisher.py` selector tuples.
- Pick thumbnail A/B/C in the Publish card before live YouTube/IG cover upload (`thumbnail_variant`).
- Live gates: gTTS-only blocked unless `ALLOW_GTTS_PUBLISH=1`; synth-only music blocked unless `ALLOW_SYNTH_MUSIC_PUBLISH=1`.

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
- Prefer quality TTS + product `image_url` + music beds for postable assets (see `docs/SOCIAL_READINESS.md`).
- Confirm `/api/readiness` music/B-roll fields and `/api/media-library` before first live publish of the day.
- Monitor terminal logs (or Sentry if configured) for render or provider errors.

## Shutdown
- Stop server terminal (`Ctrl+C`) or kill the background PID if started with `nohup`.

## Common Failures

- `ffmpeg` / `ffprobe` missing: install FFmpeg package.
- Provider errors: verify local Ollama/service availability or API keys in local env.
- Silent Shorts: enable TTS so captions and VO render.
- gTTS publish blocked: install Kokoro/Piper/OpenAI TTS or set `ALLOW_GTTS_PUBLISH=1` for emergencies only.
- Live publish blocked (no music beds): run `./scripts/fetch_operator_media.sh` or set `ALLOW_SYNTH_MUSIC_PUBLISH=1`.
- Media library empty / missing moods: check `GET /api/media-library` and drop `{mood}.wav` under `backend/assets/music/` (see ATTRIBUTION).
- Slow CPU encode: set `SHADOWCAST_FFMPEG_CODEC=auto` on an NVENC-capable ffmpeg build, or accept libx264.

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
