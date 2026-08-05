# Social posting readiness

Assessment date: 2026-08-05. Target: videos good enough to start posting on YouTube and other social platforms.

## Dual score

| Bar | Score | Meaning |
|-----|------:|---------|
| **Faceless niche** (kinetic text affiliate Shorts/long that niches already tolerate) | **~75%** | P0 shipped: TTS defaults on, music beds path, product stills/thumbs when `image_url` set, gTTS publish gate. Remaining: visual sameness without stills, long-form captions, WhisperX, platform-native packages. |
| **Mainstream affiliate** (competes on CTR with typical Amazon-review YT / TikTok) | **~55%** | Product stills + bed path + TTS gates close the worst gaps; still need real licensed music swaps, consistent product imagery from APF/Amazon, long-form SRT, native IG/TikTok packages, pre-publish QA UI. |

**Blended “first public posts without cringe”:** ~65% with quality TTS + `image_url` + replaced music beds. True ~100% still needs P1/P2 below.

P0 in this release: product stills, TTS defaults/gates, music beds, product-hero thumbs.

## What already counts

- Audio-driven TTS + inter-segment pause (`tts_generator.py`, `video_renderer.py`)
- Cosine ducking + two-pass loudnorm −14 LUFS (`sound_design.py`)
- Shorts burn-in captions + entity lower-thirds (`brand_overlays.py`)
- Style matrix + claim audit + live prompt eval 16/16
- YouTube / Meta / TikTok / Rumble publish paths

## Gap → 100% roadmap

### P0 — Unblocks “actually postable” (shipped)

1. Product stills in key segments + thumbs when `image_url` present
2. Default / smart TTS on when quality provider ready; soft-block gTTS-only live publish
3. Royalty-free / drop-in music beds under `backend/assets/music/` (synth fallback)
4. Product-hero thumbnail variant + contrast WARN via `visual_quality.py`

### P1 — Retention / platform polish

5. Long-form SRT sidecar for YouTube captions
6. Forced-align (WhisperX) behind flag for real word highlights
7. Platform-native TikTok/IG posting fields
8. Pre-publish quality checklist API/UI (claim audit + contrast + TTS + duration)

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
3. Generate with TTS on; confirm Shorts captions present
4. Drop licensed beds into `backend/assets/music/{mood}.wav` if possible
5. Eyeball one short_form + one thumbnail; contrast should not WARN
6. Publish dry-run first; live publish blocked if only gTTS unless `ALLOW_GTTS_PUBLISH=1`
