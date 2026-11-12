# Landscape + Decision Report — Video Gen, TTS Overlay, Prompt Efficiency
**Date:** 2026-08-04  
**Slug:** `video-tts-prompting-2026`  
**Decision frame:** Highest-ROI improvements for ShadowCast's assemble pipeline (script → TTS → overlays → mux), not a generic diffusion-video shopping list.

---

## Executive verdict

1. **Invert timing control:** measure TTS, then set scene duration (plus pause). Stop forcing speech into LLM-guessed slots.
2. **Finish audio post:** loudnorm ~−14 LUFS / −1 dBTP, smooth music ducking, micro-fades.
3. **Shorts captions:** burn-in, 4–7 words, UI-safe placement; word-level animation is optional and evidence is directional.
4. **Prompting:** keep stable system prefix + eval gates; add provider cache keys if on OpenAI; don't DSPy without new metrics.
5. **Skip for now:** Prompt Relay / SwitchCraft / lip-sync avatar padding — wrong architecture class.

---

## Hypotheses

| ID | Claim | Result |
|----|-------|--------|
| H1 | Segmented TTS + pad > monolithic | **Confirmed** — already partially implemented |
| H2 | Prompt prefix stability dominates cost/latency | **Confirmed** for cloud; local path different |
| H3 | Audio-driven scene duration > TTS provider upgrade alone | **Confirmed** |
| H4 | Diffusion temporal-control papers low near-term ROI | **Confirmed** |

---

## Method map (ranked for ShadowCast)

### P0 — Do next

| Method | Why | Evidence |
|--------|-----|----------|
| Audio-driven segment duration | Preserves prosody; kills trim artifacts | F1, F3; sources 06,07,15 |
| Shared timestamp CSV → captions + overlays | One clock for VO, captions, lower-thirds | 06,12 |
| loudnorm + true-peak limit | Platform-safe levels | 04,05,18 |
| Cosine-ease / sidechain ducking | Music under VO without clicks | 08 |

### P1 — High value when shipping Shorts hard

| Method | Why | Evidence |
|--------|-----|----------|
| Burn-in captions, 4–7 words, upper-mid safe zone | Muted viewing; UI chrome | 10,11,12 |
| Word-level highlight (WhisperX/forced align) | Directional retention lift | 10 (caveat: not RCT) |
| Intentional pause budget 200–500ms between segments | Cut on breath points | 06,07 |

### P2 — Prompt efficiency (mostly polish)

| Method | Why | Evidence |
|--------|-----|----------|
| Keep system static; RAG/product at end | Cache hits | 03,16 |
| `prompt_cache_key` / explicit breakpoints (OpenAI) | Hit rate + avoid write waste | 03 |
| Eval-gated edits only; few-shot on parse failure clusters | Quality without token bloat | 14,16 |
| Strict JSON / constrained decoding on cloud path | Fewer retries | 14 |

### Watch list — not now

| Method | Why wait |
|--------|----------|
| Prompt Relay / SwitchCraft | Diffusion attention routing; no MoviePy path |
| Avatar lip-sync lead silence 300–500ms | Overlay pipeline, not faces |
| Full DSPy MIPROv2 rewrite | Need new metric + trainset; current eval already green |
| Gen-video model hop (Kling/Veo/Wan) | Different product unless B-roll strategy changes |

---

## Adversarial pass

1. **What if LLM durations are already accurate?** Then audio-driven change is smaller — but TTS trim still harms naturalness; measure before/after WER-ish listener tests on 10 clips.
2. **What if caption % lifts are vendor marketing?** Source 10 agrees. Ship *any* readable burn-in first; treat karaoke animation as A/B, not gospel.
3. **What if prompt caching is irrelevant on Ollama?** True for cost. Still keep prefix order for future cloud and for cognitive prompt structure.
4. **What if gen-video B-roll becomes core?** Reopen H4; temporal segmented prompts then matter.

---

## ShadowCast-specific gap analysis

| Area | Current | Research target |
|------|---------|-----------------|
| TTS | Per-segment generate; trim/pad to LLM `duration` | Pad scene to audio; optional rate adjust only if over max |
| Contract | ~2.5–3 wps fit duration | Duration = audio_len + pause |
| Audio master | Remux trim/pad to video | loudnorm + ducking pass |
| Captions | Overlay/text styles exist | Word timing from same segment clock; Shorts placement rules |
| Prompts | System/user split, RAG, eval 16/16 | Cache keys if OpenAI; no prose churn |

---

## Source triangulation summary

- **H1:** academic N/A · practitioner 06,07 · local primary 15 → ≥3 types if counting local+two practitioner; flag thin on academic (mechanism is engineering, not papered).
- **H2:** primary OpenAI 03 · industry 17 · local 16.
- **H3:** practitioner 06,07 · industry caption timing 12 · local 15.
- **H4:** academic 01,02 · decision against project architecture 15,16.

Insufficient evidence flagged: exact % retention for word-by-word captions (vendor-only).

---

## Recommended experiment sequence (minimal)

1. Pick 5 short_form honest_review renders.
2. Branch A: current LLM-duration TTS trim.
3. Branch B: TTS first → duration = audio + 0.35s pause → re-render visuals.
4. Score: speech cut-off count, listener naturalness 1–5, total length delta.
5. Add loudnorm on B; re-check YouTube Stats for Nerds gain.
6. Optional: burn-in 5-word captions on B for muted watch test.

---

## Files in this investigation

- `plan.md`, `sources.csv`, `sources/*.md`, `findings/*.md`, `refresh_targets.md`


---

## Subagent merge addendum (2026-08-04)

Integrated [Research video assemble quality](a2b07a55-c3e3-4137-a648-f21c9fb974ac), [Research TTS A/V sync](b209900d-63c7-415c-9ca0-561859fca12d), [Research prompt efficiency](d34fa31f-1dfa-49e3-8bb2-63772b6d6652).

### Pipeline order (refined)

1. Script → scene CSV @ ~2.5 wps + pause markers  
2. TTS per scene → measure duration  
3. Subtitles from same CSV + word boundaries + cumulative offset  
4. Scene render: pad/trim (`apad`/`atrim`/`tpad`); VO drives length  
5. Micro-crossfade (30–50 ms) between VO segments  
6. Concat demuxer (matched codecs)  
7. Sidechain duck bed under VO  
8. Two-pass `loudnorm=I=-14:TP=-1` on final mix  
9. Optional `aresample=async=1000` for mobile drift insurance  

### New caveats

- Segmented TTS needs seam treatment (F7) — crossfade + final LUFS, not per-clip loudnorm.  
- Single-pass loudnorm can pump on speech — prefer two-pass for VOD.  
- YouTube is downward-only: masters quieter than −14 LUFS stay quiet.  
- OpenAI schema churn / dynamic system fields kill cache; Anthropic breakpoint on product block = write forever.  
- Ollama: `keep_alive: -1` for batch; speculative decode ≠ prefix cache.

### Build order (unchanged priority)

1. TTS → timestamps → scene duration map  
2. Caption template (safe zone)  
3. Phrase-boundary B-roll slotter  
4. Aspect presets 9:16 vs 16:9  
5. Entity lower-thirds on first mention  
6. Long-form chapters from segment indices only  

Sources now: **31**. Findings: F1–F9.
