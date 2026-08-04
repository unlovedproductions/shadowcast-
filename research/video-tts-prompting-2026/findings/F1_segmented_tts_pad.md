# F1 — Segmented TTS + pad-to-duration beats monolithic remux

**Status:** CONFIRMED (H1)
**Sources:** 06, 07, 08, 15 (ShadowCast already generates per-segment TTS)

## Thesis
Per-scene TTS with each audio clip padded/trimmed to the scene's timeline duration prevents cumulative A/V drift. Concatenating raw unpadded clips drifts earlier after each cut.

## ShadowCast delta
Already per-segment. Current contract is **LLM duration → force TTS into slot** (trim/pad). Higher ROI inversion: **measure TTS duration → set scene duration** (plus intentional pause), then recompute total. Trimming speech to fit fixed slots destroys prosody.

## Caveat
Monolithic TTS can win for single continuous talking-head takes with no cuts; ShadowCast is cut-heavy.
