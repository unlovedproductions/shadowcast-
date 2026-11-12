# Plan — Video generation, TTS overlay, prompting efficiency

**Date:** 2026-08-04  
**Depth:** deep  
**Genre:** landscape + decision (actionable methods for ShadowCast)

## Reframe

**Surface ask:** methods that improve video generation, TTS overlay, prompting efficiency.

**Underlying decision:** Which improvements are highest-ROI for ShadowCast’s current assemble pipeline (LLM script → TTS → brand overlays → ffmpeg mux → publish), vs. chasing foundation-model video gen that does not match the product?

**Falsifiable hypotheses**

1. **H1 — Segmented TTS > monolithic VO:** Per-scene TTS + pad-to-duration eliminates cumulative A/V drift better than one long voiceover remuxed to a fixed video timeline.
2. **H2 — Prompt prefix stability dominates cost/latency:** For script generation, static system + style rules at the front (cache-friendly) beats further prompt wording tweaks once eval gates are green.
3. **H3 — Overlay/caption timing from audio duration beats fixed slot durations:** Driving scene length from measured TTS duration (plus intentional pause) improves perceived quality more than upgrading TTS provider alone.
4. **H4 — Diffusion multi-event methods are low-ROI for ShadowCast now:** Inference-time temporal control (Prompt Relay, SwitchCraft) matters for gen-video products; for product-review assemble pipelines, B-roll/template consistency and audio post matter more.

## Scope

**In:** TTS sync/ducking/loudness, caption/overlay timing, script prompt efficiency (caching, eval, RAG placement), assemble-pipeline video quality, relevant gen-video methods as “watch list.”

**Out:** Full rewrite of job queue architecture; frontend redesign; paid SaaS bake-offs without open docs; training custom video models.

## Sourcing strategy

- Academic: arXiv temporal video control (2025–2026)
- Industry/primary: OpenAI prompt caching docs, EBU/YouTube loudness, ffmpeg patterns
- Practitioner: production TTS/video workflow writeups, open skill recipes
- Project-local: ShadowCast `future-improvements/`, `eval/AUDIT.md`, renderer contract

## Opposition queries

- When does monolithic TTS outperform segmented?
- When does prompt caching fail (RAG at front, low QPS)?
- Why gen-video “better prompting” won’t fix affiliate review assembly?

## Stop criteria

≥12 scored sources across ≥3 types per major thesis; adversarial pass complete; refresh_targets written; canvas + report delivered.
