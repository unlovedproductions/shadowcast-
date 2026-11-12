# Renderer Contract for Script LLMs

Scripts drive MoviePy rendering. Follow this contract so video matches intent.

## Duration

- Sequencing uses each segment `duration` only.
- `start_time` and `chapter_start_time` are advisory; the renderer ignores them for ordering.
- Set `total_duration_seconds` to the sum of all segment durations.
- Intro, outro, transitions, and engagement cards are added by the renderer (chrome).
- Short-form segment duration: 1.0–1.5 seconds (4–6 words).
- Long-form segment duration: 3.0–5.0 seconds (5–15 words; prefer ≤12 on-screen).
- First short-form segment: scroll-stopping hook (`headline_bold` + `impact_scale`/`pop_in`).
- **When TTS is enabled:** the renderer generates voiceover first and **rewrites** each segment `duration` to measured speech length + inter-segment pause (~0.35s). LLM duration guesses are not used to trim speech. A `{hook}_{format}_voiceover_timing.json` sidecar stores the shared clock for captions/overlays.

## Required layouts by style

| content_style | Required layout segments |
|---------------|--------------------------|
| elimination | winner_reveal |
| vs_battle | vs_split AND scorecard AND winner_reveal |
| budget_challenge | price_compare |

Optional for vs_battle: spec_compare.

## TTS-safe text

- `text` is spoken when TTS is enabled: no emoji, pronounceable, fit duration at ~2.5–3 words/sec.
- Layout segments should keep `text` short; product names live in layout fields.

## Animation map

- Hook / headlines: impact_scale or pop_in
- Stats (stat_number): impact_scale
- Cons / elimination: shake
- Layout segments: fade_in with transition fade or cut (kinetic animations are ignored on layouts)
- Avoid highlight_sweep on short-form

## Canonical text_style

Use: headline_bold, subtitle, accent_pop, cta_button, stat_number, question, pros, cons, verdict, elimination, comparison, scorecard.

Omit `visual_note` (unused by the renderer).
