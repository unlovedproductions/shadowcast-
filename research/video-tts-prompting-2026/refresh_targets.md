# Refresh targets — video-tts-prompting-2026

## Entities to re-check
- OpenAI Prompt Caching + GPT-5.6+ breakpoint/write pricing
- Anthropic/Gemini cache TTL and pricing
- YouTube integrated loudness target (still ~−14 LUFS?)
- Prompt Relay / SwitchCraft / Wan / Kling latest inference-time control papers
- WhisperX / forced-alignment tools for word-level captions
- ShadowCast `RENDERER_CONTRACT.md` duration model (LLM-driven vs audio-driven)

## Numbers to refresh
- Cached vs uncached input token price ratios
- Min tokens for cache eligibility (1024+)
- Caption retention % claims (treat as directional until RCT)
- EBU −23 vs platform −14 LUFS mapping

## Hypothesis watch
- H1–H4 status if pipeline inverts to audio-driven duration
- Whether OpenAI path is used enough for cache_key ROI
- If gen-video B-roll enters product roadmap

## Adversarial triggers (re-open research if)
- ShadowCast ships talking-head avatars (lip-sync padding becomes high ROI)
- Live eval JSON parse rate drops below baseline
- Platform Shorts UI overlay zones change caption safe area

## Added after subagent merge
- Anthropic/Gemini official cache pricing + breakpoint traps
- Ollama keep_alive / PREFILL_CACHE / speculative decode status
- Two-pass loudnorm vs single-pass pumping
- TTS segment seam/timbre drift mitigations
- YouTube Shorts safe-zone pixel maps (UI chrome changes)

## Status note (2026-08-05)

P0 items from this investigation (audio-driven TTS, loudnorm/ducking, Shorts captions, lower-thirds) are implemented in the live assemble pipeline. Treat remaining findings as P1+ backlog; see docs/SOCIAL_READINESS.md.
