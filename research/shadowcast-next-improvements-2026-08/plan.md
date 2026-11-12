# Plan — ShadowCast next improvements (video-first)

**Date:** 2026-08-12  
**Depth:** deep  
**Genre:** landscape + decision  
**Slug:** `shadowcast-next-improvements-2026-08`

## Reframe

**Surface ask:** Improve ShadowCast in any way possible, especially the video generation pipeline.

**Underlying decision:** After P0–P2 ship (audio-driven TTS, loudnorm/ducking, captions, claim audit), what ranked backlog measurably raises perceived video quality, publish success, or operator throughput — without violating assemble-pipeline product boundaries (kinetic affiliate, not Remotion/diffusion/talking-head)?

## Falsifiable hypotheses

1. **H5 — Media library > compositor migration:** Automating licensed music/B-roll/still acquisition and gating beats switching MoviePy for Remotion/ffmpeg-only for mainstream CTR in the next 1–2 quarters.
2. **H6 — Visual variety within MoviePy still has headroom:** Template packs (motion presets, product-still choreography, B-roll pacing, thumbnail contrast) raise quality more than new TTS providers at current readiness.
3. **H7 — Upstream research quality dominates post-render polish:** Better Amazon review themes + YouTube keyword/title research moves CTR more than another audio mux tweak.
4. **H8 — Fail-fast / stage recovery > parallel MoviePy:** Catching LLM/TTS/media failures before full render, plus partial job recovery, saves more wall-clock and credits than horizontal render scale.

## Scope

**In:** Video assemble-pipeline quality (MoviePy/ffmpeg/B-roll/thumbs/templates), TTS next-step (not re-litigating audio-driven timing), research→script enrichment, fail-fast/ops reliability, operator media workflows, counter-evidence for gen-video/Remotion.

**Out:** Implementing code in this run; paid SaaS bake-offs without open docs; training custom video models; full Redis/Celery rewrite design beyond documenting trigger criteria; re-proving H1–H4 from `video-tts-prompting-2026`.

## Prior work baseline

`research/video-tts-prompting-2026/` — H1–H4 confirmed; P0 TTS/audio/captions shipped (see `docs/SOCIAL_READINESS.md` 2026-08-06).

## Sourcing strategy

- Primary/local: SOCIAL_READINESS, ARCHITECTURE, future-improvements, video_renderer, amazon_scraper, youtube_research, job_store
- Industry: YouTube/TikTok creator retention guidance, stock-media licensing norms
- Practitioner: MoviePy/Remotion/ffmpeg production writeups, affiliate Shorts workflows
- Academic/standards: loudness already covered; seek retention/thumbnail A/B where available
- Live: Sentry org errors if available; Context7 for MoviePy/ffmpeg APIs

## Opposition queries

- When does a Remotion/compositor rewrite beat MoviePy incremental work?
- When does more render polish fail because hooks/scripts/thumbs are weak?
- Evidence that operator media ceiling is overstated vs product UX/auth/research bugs?

## Risk register

| Risk | Mitigation |
|------|------------|
| Re-researching shipped P0s | Explicit baseline exclusion |
| Vendor retention % marketing | Flag as directional; require triangulation |
| Thin academic coverage for affiliate craft | Accept practitioner+primary; mark under-determined |
| Scope explosion “improve anything” | Rank by ROI against H5–H8; watch-list the rest |

## Stop criteria

- ≥12 scored sources; ≥3 types per major thesis or explicit under-determined
- Adversarial pass complete; H5–H8 status set
- `refresh_targets.md` + `2026-08-12_landscape.md` written
- Claims bound to `sources/NN_*.md`

## Changelog

- 2026-08-12: Investigation opened; plan locked.
