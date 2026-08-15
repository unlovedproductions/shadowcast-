# Mock Script Exemplars

Reference script structures from eval fixtures (`backend/eval/fixtures/mock_scripts.json`).

## honest_review (long_form)

- Chapters: The Good, The Bad, Verdict
- Pros segments: battery life, ANC performance
- Cons segments: fit issues, plasticky case
- Verdict segment with CTA

## vs_battle (long_form)

- Round 1 with vs_split layout comparing products
- spec_compare layout for price contrast
- scorecard segment with value winner
- Competitor names populated from APF or manual input

## Layout segment requirements by style

| content_style | Required layout segments |
|---------------|-------------------------|
| elimination | winner_reveal before final CTA |
| vs_battle | vs_split AND scorecard AND winner_reveal (spec_compare optional) |
| budget_challenge | price_compare |
| worth_it_or_waste | verdict styling |
| honest_review | pros/cons text_style only |
| standard | hook → features → CTA |

See also `RENDERER_CONTRACT.md` for duration sum, TTS-safe text, and animation map.
