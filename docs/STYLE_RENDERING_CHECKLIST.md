# ShadowCast Style Rendering — Manual Test Checklist

Local verification matrix for all 6 content styles × 2 video formats. No full video renders required — confirm script JSON, layout segments, and thumbnail badge only.

## Prerequisites

- ShadowCast backend running (`localhost:8000`)
- APF enrichment completed on at least one test product
- Product imported via `pnpm run shadowcast:send <id> --open` or manual APF JSON paste

## Style × Format Matrix

| content_style | short_form | long_form | Has layout segments | Thumbnail badge |
|--------------|-----------|-----------|--------------------|-----------------|
| honest_review | [ ] pass | [ ] pass | N/A | HONEST REVIEW |
| elimination | [ ] pass | [ ] pass | winner_reveal | ELIMINATION |
| vs_battle | [ ] pass | [ ] pass | vs_split + scorecard | VS BATTLE |
| budget_challenge | [ ] pass | [ ] pass | price_compare | BUDGET PICK |
| worth_it_or_waste | [ ] pass | [ ] pass | verdict styling | WORTH IT? |
| standard | [ ] pass | [ ] pass | N/A | none |

## Per-Style Checks

For each style, select it in the ShadowCast UI (or confirm APF pre-selection), then generate scripts for both formats.

### honest_review

- [ ] Script uses pros/cons text_style segments
- [ ] No layout segments required
- [ ] Thumbnail shows **HONEST REVIEW** badge

### elimination

- [ ] Script includes `winner_reveal` layout segment before final CTA
- [ ] Elimination segments use `text_style: "elimination"`
- [ ] Thumbnail shows **ELIMINATION** badge

### vs_battle

- [ ] Script includes `vs_split` opener
- [ ] Script includes `scorecard` segment
- [ ] Competitors populated (from APF or manual)
- [ ] Thumbnail shows **VS BATTLE** badge

### budget_challenge

- [ ] Script includes `price_compare` layout segment
- [ ] Price field populated from APF `price_display` or fallback
- [ ] Thumbnail shows **BUDGET PICK** badge

### worth_it_or_waste

- [ ] Verdict chapter uses `text_style: "verdict"`
- [ ] Thumbnail shows **WORTH IT?** badge

### standard

- [ ] Standard promo structure (hook → features → CTA)
- [ ] No layout segments required
- [ ] Thumbnail has no style badge

## End-to-End APF Flow

1. [ ] Run APF enrichment on a test product (`review-enrichment-worker.mjs`)
2. [ ] `pnpm run shadowcast:send <id> --open` from APF repo
3. [ ] ShadowCast UI pre-selects `recommended_content_style` from enrichment
4. [ ] Competitors populated from `suggested_competitors` (not vendor name)
5. [ ] Price shows `price_display` from enrichment
6. [ ] Override style in UI, regenerate — script JSON and badge change accordingly

## Quick Script JSON Spot-Checks

After generation, inspect saved script JSON under `output/`:

| Style | Look for in segments |
|-------|---------------------|
| vs_battle | `"layout": "vs_split"`, `"layout": "scorecard"` |
| elimination | `"layout": "winner_reveal"`, `"text_style": "elimination"` |
| budget_challenge | `"layout": "price_compare"` |
| worth_it_or_waste | `"text_style": "verdict"` |

## Automated Tests

```bash
cd shadowcast-
.venv/bin/python -m pytest tests/test_content_styles.py tests/test_script_postprocessor.py tests/test_apf_import.py -q
```

Expected: all tests pass (12 total).

## Video Claim Audit

Run the artifact audit to verify rendered MP4 files against code-level claims (resolution, format pairing, layout requirements, duration drift, and unsupported animation/transition tokens):

```bash
cd shadowcast-
.venv/bin/python backend/video_claim_audit.py
```

Optional strict mode (fail on warnings too):

```bash
cd shadowcast-
.venv/bin/python backend/video_claim_audit.py --fail-on warn --require-videos
```
