# Buyer-Facing Language Rules

Script and YouTube asset prompts enforce shopper-focused language. These rules are injected via `backend/prompts.py`.

## Banned affiliate-facing language

Never mention in scripts or YouTube assets:

- commission rates
- EPC (earnings per click)
- hop conversion
- promoting the product as an affiliate
- earning as an affiliate

## Required buyer-focused framing

- Speak to shoppers considering a purchase, NOT affiliate marketers
- Use research-based language: "reviewers say", "specs show", "data proves"
- For honest/trust styles: include at least ONE con or limitation
- Titles should help shoppers decide, not hype affiliate earnings
- Tags should target buyer-intent keywords (people ready to research or purchase)
- Pinned comments must answer buyer objections and include the product link once, naturally

## Content style selection

| Use case | Recommended style |
|----------|-------------------|
| Competitor comparison videos | `vs_battle` — includes vs_split opener and scorecard segments |
| Head-to-head elimination | `elimination` — winner_reveal layout segment |
| Budget-focused picks | `budget_challenge` — price_compare layout |
| Honest pros/cons reviews | `honest_review` — pros and cons text_style segments |
| Worth-it verdict | `worth_it_or_waste` — verdict chapter styling |

See `STYLE_RENDERING_CHECKLIST.md` for the full 6-style × 2-format verification matrix.
