# F9 — Safe zones, lower-thirds, chapter timing

**Status:** CONFIRMED (assemble subagent)
**Sources:** 31, industry Shorts layout sources from assemble research

## Thesis
Shorts: keep critical text in center ~80% / mid third; avoid bottom UI and right action rail. Lower-thirds: 4–7s hold, trigger on first entity mention ±0.2–0.5s. Chapters from transcript segment indices, never LLM-invented timestamps. Progress bars: long-form only; skip on Shorts when captions present.

## Transfer from Prompt Relay
Borrow segment scheduling (global theme + local scene prompts sized by TTS duration). Do not port diffusion attention hooks.
