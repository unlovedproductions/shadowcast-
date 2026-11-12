# Landscape + Decision Report — ShadowCast next improvements (video-first)

**Date:** 2026-08-12  
**Slug:** `shadowcast-next-improvements-2026-08`  
**Depth:** deep  
**Decision frame:** After P0–P2 ship (audio-driven TTS, loudnorm/ducking, captions), what ranked backlog raises perceived quality, CTR, and throughput without violating assemble-pipeline boundaries?

**Prior baseline:** `research/video-tts-prompting-2026/` (H1–H4 confirmed; P0 TTS/audio shipped). Not re-litigated here.

---

## Executive verdict

1. **Stock the media library and gate on it** — mainstream ceiling (~75%) is operator beds/stills/B-roll, not MoviePy.
2. **Fix upstream research → script** — replace Amazon theme stubs; move beyond autocomplete-only YouTube research; enforce FTC/Associates disclosure and claim bounds.
3. **Exploit MoviePy visual headroom** — 2–3s pattern interrupts, short overlays, product-still choreography, thumb A/B — before new TTS providers.
4. **Fail-fast before render** — validate scripts/TTS/media; cache stage artifacts. Do **not** introduce Redis/Celery or Remotion yet.
5. **Skip / watch:** Remotion rewrite, diffusion gen-video B-roll, talking-head product pivot, SSML/provider hop (P2 only).

---

## Hypotheses

| ID | Claim | Result | Finding |
|----|-------|--------|---------|
| H5 | Media library > compositor migration | **Confirmed** (nuance: accessibility of assets) | F10 |
| H6 | Visual variety in MoviePy > new TTS | **Confirmed** | F11 |
| H7 | Upstream research > post-render polish | **Confirmed** | F12 |
| H8 | Fail-fast/stage recovery > parallel MoviePy | **Confirmed** (scoped; no full DAG yet) | F13 |

---

## Method map (ranked for ShadowCast)

### P0 — Do next

| Action | Why | Maps to | Evidence |
|--------|-----|---------|----------|
| Operator media pack + fetch/convert automation for `assets/music/` + `assets/broll/` | Closes documented mainstream gap | `ATTRIBUTION.md`, readiness | 01, 03, 14, 20 |
| Pre-publish / pre-render gate: quality TTS + `image_url` + real music bed present | Stops “procedural + synth” posts | `GET /api/readiness`, publish QA | 01, 26 |
| Replace Amazon `common_*_themes` stubs with real topics (SP-API or local NLP) | Honest review specificity | `amazon_scraper.py`, `research_enrichment.py` | 04, 22, 23 |
| Affiliate disclosure in VO script + description template | Compliance + trust | youtube assets / prompts | 11, 33, 23 |

### P1 — High value

| Action | Why | Maps to | Evidence |
|--------|-----|---------|----------|
| Kinetic template presets: visual change ≤2–3s; 4–6 word overlays; first-frame hook still | Retention without Remotion | `kinetic_effects.py`, `video_renderer.py` | 15, 18, 19, 07 |
| Thumb A/B already present — enforce pick + CTR truth (no clickbait mismatch) | Packaging | `thumbnail_generator.py` | 16, 17 |
| YouTube research upgrade: Trends/content-gap guidance + selective `search.list` | Better titles/hooks | `youtube_research.py` | 05, 24, 25 |
| Stage artifact cache: skip re-TTS/re-render when only package/thumb fails | Wall-clock | `app.py`, `job_store.py` | 02, 09, 26, 32 |
| Optional NVENC for final ffmpeg encode if GPU present | Speed without compositor swap | `sound_design` / write path | 13 |

### P2 — Polish

| Action | Why | Evidence |
|--------|-----|----------|
| SSML / pronunciation for product names (provider-aware) | Consistency | 10, Polly SSML limits (track C) |
| Segment crossfade / energy continuity (prior F7) | Seam hygiene | 21 |
| Media library UX (tag/search beds) so “scarcity” isn’t findability | Counter 29 | 29 |

### Watch list — not now

| Item | Reopen if |
|------|-----------|
| Remotion / React compositor | Multi-brand design system + React shop + Studio preview required (12, 28) |
| Gen-video B-roll | Template slots cannot source category footage; cost/claim risk accepted (14) |
| Talking-head avatars | Product strategy shifts from kinetic faceless (30) |
| Redis/Celery full staging | ≥2 rewrite triggers from `00-full-rewrite-summary.md` fire (02, 31) |

---

## ShadowCast gap analysis

| Area | Current | Research target |
|------|---------|-----------------|
| Media | Mixkit docs; WAVs gitignored; synth fallback | Stocked beds + hard gate for live publish |
| Visual | Kinetic + stills + optional B-roll | Preset packs / interrupt cadence |
| Research | Amazon themes stub; YT suggest API | SP-API topics + Trends-informed titles |
| Claims | Claim audit exists | Wire review themes + FTC disclosure into scripts |
| Ops | In-process job; scripts cached partially | Explicit pre-render fail-fast + stage skip |
| Compositor | MoviePy 2 + ffmpeg | Keep; accelerate ffmpeg only |

---

## Adversarial pass

1. **What if media library is already “enough” and CTR still sucks?**  
   Then H5 is incomplete — packaging/hooks (H6/H7) dominate. YouTube’s own clickbait FAQ (17) and recommendation doc (07) say so. Steel-man: do a 10-video A/B with identical media, varied hooks/titles before buying more stock.

2. **What if Remotion would unlock better motion and thus retention?**  
   Possible for design-heavy multi-template orgs (12, 28). ShadowCast is Python kinetic affiliate; TikTok even prefers less polish (18). Cost of Node/React toolchain + rewrite risk exceeds incremental MoviePy presets until multi-brand requirement appears.

3. **What if operator media ceiling is overstated (29)?**  
   Partially true — findability/reuse UX matters. That still points to media *ops*, not compositor migration. Confirmed H5 with accessibility nuance.

4. **What if talking-head converts better (30)?**  
   Credible for some affiliate niches. That is a **product-class change**, not an improvement to the kinetic pipeline. Keep on watch-list; do not smuggle into MoviePy backlog.

5. **What if fail-fast is premature optimization given quiet Sentry (31)?**  
   Fair — no live fire. Still cheap: validate before 10–30 min renders. MpegFlow itself says stay on scripts when volume is constrained (09). Prefer checkpoints over Celery (27).

---

## Source triangulation summary

| Thesis | Types used | Status |
|--------|------------|--------|
| H5 | primary local, primary NVIDIA, industry template/AI, practitioner Remotion/MoviePy | ≥3 types |
| H6 | primary YouTube/TikTok, practitioner retention | ≥3 types (practitioner % directional) |
| H7 | primary local, Amazon, FTC, YouTube | ≥3 types |
| H8 | primary local + Sentry, industry DAG, practitioner fail-fast/Celery | ≥3 types |

**Insufficient evidence flagged:** Exact retention % lifts from 2–3s cadence (19) — directional only. Talking-head revenue claims (30) — single-blog, high bias.

**Citation verify (spot-check):** YouTube Help 16559650, 9314415, 12340300, 7628154, 11914225, 11962757 fetched; MoviePy Context7 `/zulko/moviepy`; FTC Q&A fetched; MpegFlow DAG fetched 2026-05-05; NVIDIA NVENC docs cited by subagent; Amazon SP-API review topics cited by subagent.

---

## Recommended experiment sequence (minimal)

1. Stock 4 mood WAVs + ≥3 B-roll MP4s; gate live publish if synth-only.  
2. Ship 10 Shorts: 5 with current themes vs 5 with manually filled praise/complaint themes (proxy for SP-API). Measure stayed-to-watch + AVD.  
3. Same product: 3 hook variants × same media; pick winner (YouTube-native A/B).  
4. Add pre-render checklist failures in logs; measure wasted render minutes for one week.  
5. Only if (4) shows repeated mid-pipeline loss **and** concurrency SLA pain → revisit staged rewrite triggers.

---

## Top 5 actions (chat verdict mirror)

1. Media pack + publish gate  
2. Real review themes + disclosure templates  
3. Kinetic interrupt presets + thumb truthfulness  
4. YouTube research beyond autocomplete  
5. Pre-render fail-fast / stage skip  

**Do not:** Remotion, Celery, gen-video, new TTS provider as P0.
