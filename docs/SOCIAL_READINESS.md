# Social posting readiness

Assessment date: 2026-08-14 (H5–H8 research pack shipped on `cursor/ops-docs`). Target: videos good enough to start posting on YouTube and other social platforms.

## Dual score

| Bar | Score | Meaning |
|-----|------:|---------|
| **Faceless niche** (kinetic text affiliate Shorts/long that niches already tolerate) | **~90%** | P0–P2 + H5–H8 code path. Remaining: licensed beds / real stock footage on disk. |
| **Mainstream affiliate** (competes on CTR with typical Amazon-review YT / TikTok) | **~75%** | Captions + QA + gates complete; ceiling is operator media library quality. |

**Blended “first public posts without cringe”:** ~82% with quality TTS + `image_url` + music/B-roll drops + SRT/burn-in + thumb pick. True ~100% needs operator-supplied licensed media, not more code.

Plan P0–P2 + research H5–H8 shipped in code. Operator media binaries remain the ceiling.

## What already counts

- Audio-driven TTS + inter-segment pause (`tts_generator.py`, `video_renderer.py`)
- TTS pronunciation lexicon + RMS seam matching (`tts_pronounce.py`; `SHADOWCAST_TTS_PRONUNCIATIONS`)
- Cosine ducking + two-pass loudnorm −14 LUFS (`sound_design.py`)
- Shorts burn-in captions + entity lower-thirds (`brand_overlays.py`)
- Optional WhisperX word-align for karaoke highlights (`whisperx_align.py`)
- Long-form burn-in captions when TTS on (`SHADOWCAST_LONGFORM_BURNIN`, default on) + `.srt` sidecars
- Short-form kinetic presets: ≤6-word overlays, 1.0–1.5s beats, first-frame hook (`script_postprocessor.py`)
- Product-still hero cadence every 3rd beat (`product_media.py`)
- Optional NVENC final encode (`SHADOWCAST_FFMPEG_CODEC=auto`)
- Optional long-form B-roll chapter pads (`broll.py`, `assets/broll/`)
- Media library inventory / search (`GET /api/media-library`) + readiness missing moods/tags
- Music-bed hard gate for live publish (`ALLOW_SYNTH_MUSIC_PUBLISH` escape)
- Amazon review themes + FTC shopper disclosure prompts
- YouTube research title angles / content gaps (+ optional Data API key)
- Platform-native IG Reels / TikTok `post_info` fields (`posting_package_adapter.py`)
- Pre-publish QA including **claim audit** + contrast + TTS + duration + thumb packaging (`POST /api/publish/quality`)
- Hardened Rumble Playwright selector fallbacks + dry-run docs
- Style matrix + claim audit + live prompt eval 16/16
- YouTube / Meta / TikTok / Rumble publish paths

## Gap → 100% roadmap

### P0 — Unblocks “actually postable” (shipped)

1. Product stills in key segments + thumbs when `image_url` present
2. Default / smart TTS on when quality provider ready; soft-block gTTS-only live publish
3. Royalty-free / drop-in music beds under `backend/assets/music/` (run `scripts/fetch_operator_media.sh`; synth fallback soft-blocked for live publish unless `ALLOW_SYNTH_MUSIC_PUBLISH=1`)
4. Product-hero thumbnail variant + contrast WARN via `visual_quality.py`
5. Amazon review themes + FTC affiliate disclosure in scripts/packages

### P1 — Retention / platform polish (shipped)

1. Long-form SRT sidecar for YouTube captions (also short_form) + long-form burn-in captions
2. Forced-align (WhisperX) behind `SHADOWCAST_WHISPERX_ALIGN=1`
3. Platform-native TikTok/IG posting fields
4. Pre-publish quality checklist API/UI (TTS + duration + captions + contrast + **claim audit** + thumb packaging)
5. Kinetic presets + YT research angles + render fail-fast + optional NVENC

### P2 — Differentiation (shipped)

1. Optional stock B-roll for long-form chapter pads (`SHADOWCAST_BROLL` / `assets/broll/`)
2. Explicit A/B/C thumb pick-before-publish (Publish card + `thumbnail_variant`)
3. Harden Rumble Playwright selectors + dry-run vs live docs in RUNBOOK
4. TTS pronounce lexicon + VO seam energy matching
5. Media library tag/search (`GET /api/media-library`) so missing beds are findable

### Out of scope (wrong product class)

- Diffusion gen-video / Remotion / talking-head lip-sync unless strategy changes
- Full staged rewrite (`future-improvements/`) — ops scale, not posting quality

## Operator checklist before first public post

1. `/api/readiness` → `ready`, `tts_quality: true`; check `music_beds` / `music_beds_missing` / `broll_missing`
2. `GET /api/media-library` (or `?q=mood`) — confirm expected beds/clips present
3. Product `image_url` set (UI/CSV) **or** APF import with vendor sales/offer page URLs
4. Generate with TTS on; confirm Shorts captions + `.srt` beside MP4
5. Prefer `./scripts/fetch_operator_media.sh` for Mixkit music + B-roll; or drop licensed beds into `backend/assets/music/{mood}.wav`
6. Optional: drop B-roll into `backend/assets/broll/` or set `SHADOWCAST_BROLL=1`
7. Optional: `SHADOWCAST_WHISPERX_ALIGN=1` + install `whisperx`
8. Pick thumbnail A/B/C in Publish card; contrast should not WARN; thumb primary text ≤6 words
9. Run **Pre-Publish QA** — overall must not be `FAIL`
10. Publish dry-run first; live publish blocked if only gTTS unless `ALLOW_GTTS_PUBLISH=1`; blocked without music beds unless `ALLOW_SYNTH_MUSIC_PUBLISH=1`
