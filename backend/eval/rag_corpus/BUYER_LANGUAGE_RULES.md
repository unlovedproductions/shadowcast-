# Buyer-Facing Language Rules

Script and YouTube asset prompts enforce shopper-focused language. These rules are injected via `backend/prompts.py`.

## Banned affiliate-facing language

Never mention in scripts or YouTube assets:

- commission rates / EPC math
- hop conversion
- teaching viewers how to promote products as affiliates
- "earn as an affiliate" creator-howto framing

## Required shopper disclosure (FTC)

- Scripts: one short plain-language affiliate disclosure in VO (early or end CTA)
- YouTube description + pinned comment: disclose affiliate relationship; label the URL as `Paid link:` or `Affiliate link:` with a clear explanation
- Example: "This video contains affiliate links. If you buy through them, I may earn a commission at no extra cost to you."

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
| Competitor comparison videos | `vs_battle` — requires vs_split AND scorecard AND winner_reveal |
| Head-to-head elimination | `elimination` — requires winner_reveal layout segment |
| Budget-focused picks | `budget_challenge` — requires price_compare layout |
| Honest pros/cons reviews | `honest_review` — pros and cons text_style segments |
| Worth-it verdict | `worth_it_or_waste` — verdict chapter styling |

See `STYLE_RENDERING_CHECKLIST.md` for the full 6-style × 2-format verification matrix.
