# Delta — subagent merge 2026-08-04

Merged findings from:
- Research video assemble quality (a2b07a55)
- Research TTS A/V sync (b209900d)
- Research prompt efficiency (d34fa31f)

## Added
- Sources 19–31
- Findings F7 (segment TTS seams), F8 (provider cache matrix), F9 (safe zones/lower-thirds)
- Pipeline order refinements: two-pass loudnorm, concat demuxer, micro-crossfade, Ollama keep_alive

## Unchanged conclusions
H1–H4 still hold. P0 remains audio-driven duration + loudness/ducking + shared clock.
