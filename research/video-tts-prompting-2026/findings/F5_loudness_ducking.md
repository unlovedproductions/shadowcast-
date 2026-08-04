# F5 — Loudnorm + smooth ducking > louder masters

**Status:** CONFIRMED
**Sources:** 04, 05, 08, 18

## Thesis
Target ~−14 LUFS integrated for YouTube (downward-only normalization), true peak ≤ −1 dBTP. Music under VO via sidechain/cosine-ease ducking (~0.55 depth), not hard volume jumps. Speech intelligibility > max loudness.

## ShadowCast delta
Add post-mux loudnorm pass + music ducking if music bed exists. Avoid over-loud TTS competing with platform turn-down.
