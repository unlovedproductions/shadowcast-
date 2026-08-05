# Social posting readiness

Assessment date: 2026-08-05 (P1 partial refresh). Target: videos good enough to start posting on YouTube and other social platforms.

## Dual score

| Bar | Score | Meaning |
|-----|------:|---------|
| **Faceless niche** (kinetic text affiliate Shorts/long that niches already tolerate) | **~80%** | P0 + P1 SRT sidecars, native IG/TikTok payload fields, pre-publish QA API/UI. Remaining: WhisperX word-align, visual variety without stills. |
| **Mainstream affiliate** (competes on CTR with typical Amazon-review YT / TikTok) | **~60%** | Captions + platform packages + QA close more gaps; still need licensed music swaps, consistent product imagery, WhisperX, stock B-roll. |

**Blended “first public posts without cringe”:** ~70% with quality TTS + `image_url` + replaced music beds + SRT. True ~100% still needs remaining P1/P2 below.

P0 shipped. P1 partially shipped (SRT, native packages, publish QA). WhisperX still open.

## What already counts

- Audio-driven TTS + inter-segment pause (`tts_generator.py`, `video_renderer.py`)
- Cosine ducking + two-pass loudnorm −14 LUFS (`sound_design.py`)
- Shorts burn-in captions + entity lower-thirds (`brand_overlays.py`)
- Long-form/short-form `.srt` sidecars from shared TTS timing (`caption_srt.py`)
- Platform-native IG Reels / TikTok `post_info` fields (`posting_package_adapter.py`)
- Pre-publish QA: `POST /api/publish/quality` + UI button
- Style matrix + claim audit + live prompt eval 16/16
- YouTube / Meta / TikTok / Rumble publish paths

## Gap → 100% roadmap

### P0 — Unblocks “actually postable” (shipped)

1. Product stills in key segments + thumbs when `image_url` present
2. Default / smart TTS on when quality provider ready; soft-block gTTS-only live publish
3. Royalty-free / drop-in music beds under `backend/assets/music/` (synth fallback)
4. Product-hero thumbnail variant + contrast WARN via `visual_quality.py`

### P1 — Retention / platform polish

5. Long-form SRT sidecar for YouTube captions — **shipped** (also short_form)
6. Forced-align (WhisperX) behind flag for real word highlights — **open**
7. Platform-native TikTok/IG posting fields — **shipped**
8. Pre-publish quality checklist API/UI (TTS + duration + captions + contrast) — **shipped**

### P2 — Differentiation

9. Optional stock B-roll for long-form chapter pads
10. Explicit A/B thumb pick-before-publish
11. Harden Rumble Playwright selectors

### Out of scope (wrong product class)

- Diffusion gen-video / Remotion / talking-head lip-sync unless strategy changes
- Full staged rewrite (`future-improvements/`) — ops scale, not posting quality

## Operator checklist before first public post

1. `/api/readiness` → `ready`, `tts_quality: true`
2. Product `image_url` set (UI/CSV) **or** APF import with vendor sales/offer page URLs (auto og:image / product photo extract)
3. Generate with TTS on; confirm Shorts captions + `.srt` beside MP4
4. Drop licensed beds into `backend/assets/music/{mood}.wav` if possible
5. Eyeball one short_form + one thumbnail; contrast should not WARN
6. Run **Pre-Publish QA** (`POST /api/publish/quality`) — overall must not be `FAIL`
7. Publish dry-run first; live publish blocked if only gTTS unless `ALLOW_GTTS_PUBLISH=1`
