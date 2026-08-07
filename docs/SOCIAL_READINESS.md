# Social posting readiness

Assessment date: 2026-08-06 (audit rerun — plan gaps closed; code bar verified). Target: videos good enough to start posting on YouTube and other social platforms.

## Dual score

| Bar | Score | Meaning |
|-----|------:|---------|
| **Faceless niche** (kinetic text affiliate Shorts/long that niches already tolerate) | **~90%** | P0–P2 + claim-audit QA + long-form burn-in. Remaining: licensed beds / real stock footage. |
| **Mainstream affiliate** (competes on CTR with typical Amazon-review YT / TikTok) | **~75%** | Captions + QA complete; ceiling is operator media library quality. |

**Blended “first public posts without cringe”:** ~82% with quality TTS + `image_url` + music/B-roll drops + SRT/burn-in + thumb pick. True ~100% needs operator-supplied licensed media, not more code.

Plan P0–P2 shipped in code. Operator media library quality is the remaining ceiling.

## What already counts

- Audio-driven TTS + inter-segment pause (`tts_generator.py`, `video_renderer.py`)
- Cosine ducking + two-pass loudnorm −14 LUFS (`sound_design.py`)
- Shorts burn-in captions + entity lower-thirds (`brand_overlays.py`)
- Optional WhisperX word-align for karaoke highlights (`whisperx_align.py`)
- Long-form burn-in captions when TTS on (`SHADOWCAST_LONGFORM_BURNIN`, default on) + `.srt` sidecars
- Optional long-form B-roll chapter pads (`broll.py`, `assets/broll/`)
- Platform-native IG Reels / TikTok `post_info` fields (`posting_package_adapter.py`)
- Pre-publish QA including **claim audit** + contrast + TTS + duration (`POST /api/publish/quality`)
- Hardened Rumble Playwright selector fallbacks + dry-run docs
- Style matrix + claim audit + live prompt eval 16/16
- YouTube / Meta / TikTok / Rumble publish paths

## Gap → 100% roadmap

### P0 — Unblocks “actually postable” (shipped)

1. Product stills in key segments + thumbs when `image_url` present
2. Default / smart TTS on when quality provider ready; soft-block gTTS-only live publish
3. Royalty-free / drop-in music beds under `backend/assets/music/` (synth fallback)
4. Product-hero thumbnail variant + contrast WARN via `visual_quality.py`

### P1 — Retention / platform polish (shipped)

5. Long-form SRT sidecar for YouTube captions (also short_form) + long-form burn-in captions
6. Forced-align (WhisperX) behind `SHADOWCAST_WHISPERX_ALIGN=1`
7. Platform-native TikTok/IG posting fields
8. Pre-publish quality checklist API/UI (TTS + duration + captions + contrast + **claim audit**)

### P2 — Differentiation (shipped)

9. Optional stock B-roll for long-form chapter pads (`SHADOWCAST_BROLL` / `assets/broll/`)
10. Explicit A/B/C thumb pick-before-publish (Publish card + `thumbnail_variant`)
11. Harden Rumble Playwright selectors + dry-run vs live docs in RUNBOOK

### Out of scope (wrong product class)

- Diffusion gen-video / Remotion / talking-head lip-sync unless strategy changes
- Full staged rewrite (`future-improvements/`) — ops scale, not posting quality

## Operator checklist before first public post

1. `/api/readiness` → `ready`, `tts_quality: true`
2. Product `image_url` set (UI/CSV) **or** APF import with vendor sales/offer page URLs
3. Generate with TTS on; confirm Shorts captions + `.srt` beside MP4
4. Drop licensed beds into `backend/assets/music/{mood}.wav` if possible
5. Optional: drop B-roll into `backend/assets/broll/` or set `SHADOWCAST_BROLL=1`
6. Optional: `SHADOWCAST_WHISPERX_ALIGN=1` + install `whisperx`
7. Pick thumbnail A/B/C in Publish card; contrast should not WARN
8. Run **Pre-Publish QA** — overall must not be `FAIL`
9. Publish dry-run first; live publish blocked if only gTTS unless `ALLOW_GTTS_PUBLISH=1`
