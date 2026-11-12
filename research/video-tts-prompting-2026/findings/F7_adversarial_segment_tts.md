# F7 — Adversarial: segmented TTS has seam costs

**Status:** QUALIFIES H1 (does not refute)
**Sources:** 26, 01/07 prior, TTS subagent

## Thesis
Per-scene TTS wins on drift, but stitching introduces clicks, volume jumps, and timbre drift unless you add 30–50ms crossfades and normalize loudness at chapter/final mix (not per tiny segment).

## Implication for ShadowCast
Keep per-scene generation; add micro-crossfade on concat + single final loudnorm pass (two-pass preferred). Do not loudnorm each segment independently.
