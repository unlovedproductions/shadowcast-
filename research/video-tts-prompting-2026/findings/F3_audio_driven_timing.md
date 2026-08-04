# F3 — Drive scene length from measured audio, not fixed LLM slots

**Status:** CONFIRMED (H3)
**Sources:** 06, 07, 15, 12

## Thesis
Perceived quality jumps when visuals wait for speech. Fixed 1.0–1.5s short-form slots force speech compression. Better: TTS → measure duration → pad intentional pause (200–500ms) → set segment duration → align captions from same timestamps.

## Caption timing
Industry practice: slight caption lead (0.1–0.3s) or word-level sync from forced alignment. Burn-in for Shorts; SRT sidecar for long-form.

## Evidence quality on caption lift
Any captions: strong historical evidence (Verizon/Publicis 2019). Word-by-word % lifts: directional vendor claims, not controlled RCTs (source 10).
