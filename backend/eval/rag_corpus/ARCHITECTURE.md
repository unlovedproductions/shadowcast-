# ShadowCast Architecture

## Intent

ShadowCast converts structured affiliate product data into short-form (9:16) and long-form (16:9) kinetic text videos, YouTube posting packages, thumbnails, and multi-platform publish payloads.

## Runtime components

| Layer | Location | Role |
|-------|----------|------|
| API / jobs | `backend/app.py`, `job_store.py` | FastAPI, job lifecycle, artifact cache, batch workers; optional Sentry |
| Scripts | `script_generator.py`, `prompts.py`, `script_postprocessor.py`, `content_styles.py` | LLM JSON scripts + layout injection + short-form kinetic presets |
| Research / RAG | `research_enrichment.py`, `rag_store.py`, `style_rules_retrieval.py`, `youtube_research.py` | Amazon/YouTube research (review themes, title angles) + style-rules corpus |
| TTS | `tts_generator.py`, `tts_pronounce.py`, `whisperx_align.py` | Per-segment VO; pronunciation lexicon; seam crossfades; optional WhisperX karaoke |
| Render | `video_renderer.py`, `kinetic_effects.py`, `comparison_layouts.py`, `bg_generator.py`, `brand_overlays.py`, `broll.py`, `caption_srt.py` | MoviePy frames, captions, SRT, optional B-roll pads; optional NVENC encode |
| Product media | `product_media.py` | Product still download/cache + hero cadence compositing |
| Operator media | `media_library.py` | Inventory/search for music beds + B-roll (`GET /api/media-library`) |
| Audio | `sound_design.py`, `audio_options.py` | Music beds or synth, ducking, two-pass loudnorm |
| Assets | `youtube_assets_generator.py`, `thumbnail_generator.py`, `visual_quality.py` | SEO packages, thumbs, contrast audit |
| Publish | `publish_service.py`, `posting_package_adapter.py`, `publish_quality.py`, `publishers/*`, `oauth_manager.py` | Platform payloads, pre-publish QA, upload gates |
| UI | `frontend/index.html` | SPA (thumb pick, Pre-Publish QA, dry-run); optional Sentry loader |
| Quality | `video_claims.py`, `video_claim_audit.py`, `backend/eval/*`, `scripts/quality/` | Contracts, eval, CI gates |

## Key dependencies

- `fastapi`, `uvicorn` — API
- `moviepy`, `Pillow`, `numpy`, `scipy` — media
- `ffmpeg` / `ffprobe` — mux, loudnorm, social repurpose (optional `h264_nvenc`)
- Optional: `openai`, Kokoro/Piper TTS, `whisperx`, Playwright (Rumble), `sentry_sdk`

## Data flow

```mermaid
flowchart LR
  input[UI_APF_CSV] --> enrich[research_enrichment]
  enrich --> script[script_generator]
  script --> tts[tts_generator]
  tts --> render[video_renderer]
  render --> mix[sound_design]
  mix --> pkg[youtube_assets_thumbnails]
  pkg --> qa[publish_quality]
  qa --> pub[publish_service]
```

1. Input payload (UI, batch CSV, or APF import).
2. Optional research enrichment (Amazon review themes, FTC disclosure framing, YouTube angles) + style-rules RAG into script prompts.
3. Scripts generated per hook × format; postprocessor injects required layouts and short-form kinetic presets.
4. If TTS on: pronunciation map → measure speech → rewrite segment durations → inter-segment pause / energy-matched crossfade → timing sidecar + `.srt`.
5. MoviePy render (product-still hero cadence when `image_url` present) + Shorts captions / lower-thirds; optional B-roll chapter pads; optional WhisperX word highlights; final encode via libx264 or NVENC.
6. Music bed (preferred) or synth → duck under VO → two-pass loudnorm ≈ −14 LUFS.
7. YouTube package + thumbnails; pre-publish QA; publish adapters per platform (thumb A/B/C pick). Live publish hard-blocks missing music beds unless `ALLOW_SYNTH_MUSIC_PUBLISH=1`.
8. Readiness reports music/B-roll completeness; `GET /api/media-library` inventories expected moods/tags for findability.

## Env flags (selected)

| Variable | Effect |
|----------|--------|
| `HOST` / `PORT` | Bind address (default `127.0.0.1:8000`) |
| `STYLE_RULES_RAG` | `0` disables style corpus injection |
| `SHADOWCAST_BATCH_WORKERS` | Parallel batch product workers |
| `CORS_ORIGINS` / `CORS_ALLOW_ALL` | CORS |
| `INTERNAL_SERVICE_SECRET` | Mission Control / APF machine auth |
| `ALLOW_GTTS_PUBLISH` | `1` allows live publish with gTTS-only voice |
| `ALLOW_SYNTH_MUSIC_PUBLISH` | `1` allows live publish without royalty-free music beds |
| `SHADOWCAST_REQUIRE_PRODUCT_IMAGE` | `1` fails pre-publish QA when `image_url` missing |
| `SHADOWCAST_TTS_DEFAULT` | `0` forces API default TTS off |
| `SHADOWCAST_TTS_PRONUNCIATIONS` | Lexicon overrides for TTS (`word:phonetic` map) |
| `SHADOWCAST_TTS_CROSSFADE` | Inter-segment VO crossfade seconds (default `0.04`) |
| `SHADOWCAST_TTS_INTER_SEGMENT_PAUSE` | Pause between TTS segments (seconds) |
| `SHADOWCAST_WHISPERX_ALIGN` | `1` enables optional WhisperX karaoke (needs `whisperx`) |
| `SHADOWCAST_BROLL` | `1` force B-roll pads; `0` disable; unset = auto if files in `assets/broll/` |
| `SHADOWCAST_LONGFORM_BURNIN` | `0` disables long-form burn-in captions (default on when TTS) |
| `SHADOWCAST_FFMPEG_CODEC` | `auto` (default) / `libx264` / `h264_nvenc` |
| `SHADOWCAST_VIDEO_PRESET` | Encode preset name (maps to x264/NVENC presets) |
| `SENTRY_DSN` | Backend Sentry DSN (omit to disable) |
| `SENTRY_FRONTEND_DSN` | SPA loader DSN (omit strips loader script) |
| `SENTRY_ENVIRONMENT` | Sentry environment tag (default `development`) |

## Integration points

- APF direct-import payloads for product metadata (`image_url` optional / auto from sales pages)
- Mission Control orchestration via service secret
- Shared `INTERNAL_SERVICE_SECRET` for M2M requests
- Operator media via `scripts/fetch_operator_media.sh` + `GET /api/media-library`

## Non-goals (current architecture)

- Remotion / diffusion gen-video / talking-head lip-sync
- Independent stage workers / Redis-Celery (see `future-improvements/`)
