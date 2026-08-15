# ShadowCast Style Rendering — Manual Test Checklist

Local verification matrix for all 6 content styles × 2 video formats. No full video renders required — confirm script JSON, layout segments, and thumbnail badge only.

> **Automated regression:** `tests/test_style_matrix.py` covers all 6 styles × short/long layout segments and thumbnail badges; `tests/test_content_styles.py`, `tests/test_script_postprocessor.py`, `tests/test_apf_import.py`, and `tests/test_audio_options.py` cover style normalization, postprocessor injection, APF mapping, and audio mood. Manual MP4 eyeball and full APF→ShadowCast E2E still required when services are up.

## Prerequisites

- ShadowCast backend running (`localhost:8000`)
- APF enrichment completed on at least one test product
- Product imported via `pnpm run shadowcast:send <id> --open` or manual APF JSON paste

## Style × Format Matrix

| content_style | short_form | long_form | Has layout segments | Thumbnail badge |
|--------------|-----------|-----------|--------------------|-----------------|
| honest_review | [x] pass | [x] pass | N/A | HONEST REVIEW |
| elimination | [x] pass | [x] pass | winner_reveal | ELIMINATION |
| vs_battle | [x] pass | [x] pass | vs_split + scorecard + winner_reveal | VS BATTLE |
| budget_challenge | [x] pass | [x] pass | price_compare | BUDGET PICK |
| worth_it_or_waste | [x] pass | [x] pass | verdict styling | WORTH IT? |
| standard | [x] pass | [x] pass | N/A | none |

> Verified 2026-07-22 via `tests/test_style_matrix.py` (6×2 layout/badge matrix) + related style/APF/audio pytest suite. Manual MP4 eyeball still optional when services are up.

## Required layouts (retrieval)

- elimination: winner_reveal
- vs_battle: vs_split + scorecard + winner_reveal
- budget_challenge: price_compare
- worth_it_or_waste: verdict text_style

See docs/STYLE_RENDERING_CHECKLIST.md for full manual checklist.
