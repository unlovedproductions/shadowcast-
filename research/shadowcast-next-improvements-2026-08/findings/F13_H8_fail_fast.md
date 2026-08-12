# F13 — H8: Fail-fast / stage recovery > parallel MoviePy

**Status:** CONFIRMED (scoped)  
**Sources:** 02, 09, 13, 26, 27, 31, 32

## Thesis

Catching LLM/TTS/media failures before full render, plus caching successful stage artifacts, saves more wall-clock than horizontal MoviePy parallelism. Full Redis/Celery still deferred.

## Evidence

- Project: stages not independently recoverable; rewrite deferred until ≥2 triggers (02).
- Industry: scripts OK for constrained volume; DAG value is localized retry of expensive stages (09) — and vendors admit stay-on-script when costs don’t justify.
- Fail-fast: validate cheap preconditions before expensive ops (26).
- MoviePy re-render cost is structural (Python→numpy→ffmpeg) (32); NVENC helps encode, not composition (13).
- Celery often unneeded early; ops tax (27).
- Live Sentry: no unresolved render fires in 7d (31) — triggers not met.

## Scope note

“Confirmed” means prefer fail-fast checkpoints *inside* current architecture. Not “build MpegFlow now.”

## Implication

P1: pre-render gate (scripts parse, TTS quality provider, image_url/music presence); cache `*_scripts.json` / TTS wavs; skip re-render on package-only failures.
