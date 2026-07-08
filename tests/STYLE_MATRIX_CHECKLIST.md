# ShadowCast 6-Style Manual Test Matrix

Local checklist — no full video renders required. Verify script JSON, layout segments, and thumbnail badge metadata per style.

## Prerequisites

1. ShadowCast backend running (`http://localhost:8000`)
2. One APF product with review enrichment complete (`enrichment_status = complete`)
3. Optional: Mission Control import + video job for end-to-end MC path

## Matrix

| content_style | short_form | long_form | Layout segments expected | Thumbnail badge |
|---------------|-----------|-----------|--------------------------|-----------------|
| `honest_review` | [ ] pass | [ ] pass | N/A (text only) | HONEST REVIEW |
| `elimination` | [ ] pass | [ ] pass | `winner_reveal` | ELIMINATION |
| `vs_battle` | [ ] pass | [ ] pass | `vs_split`, `spec_compare`, `scorecard`, `winner_reveal` | VS BATTLE |
| `budget_challenge` | [ ] pass | [ ] pass | `price_compare` | BUDGET PICK |
| `worth_it_or_waste` | [ ] pass | [ ] pass | verdict chapter uses `text_style: verdict` | WORTH IT? |
| `standard` | [ ] pass | [ ] pass | N/A (text only) | none |

## Per-style steps (UI)

1. Load product (manual entry or APF import draft).
2. Set **Content Style** to the row style.
3. For `vs_battle` / `elimination`, confirm competitors are populated (APF import or manual).
4. Generate **short_form** only → open saved script JSON under job output.
5. Repeat for **long_form**.
6. Confirm layout segments and `text_style` aliases (`pro_point` → `pros`, etc.).
7. Note thumbnail badge text in generate response / job metadata (no MP4 render needed).

## APF end-to-end

1. Run APF enrichment on a product (`review-enrichment-worker.mjs --once`).
2. `pnpm run shadowcast:send <id> --open` (or Product Detail → Send to ShadowCast).
3. Confirm UI pre-selects `recommended_content_style` and competitors from `suggested_competitors`.
4. Override style to `vs_battle`, regenerate script JSON, confirm layout segments change.

## Mission Control path

1. Import products from APF (enriched payload stored).
2. Queue video job for imported product.
3. Confirm `/api/generate` payload includes full `product_info` + `content_style` (not thin stub).

## Automated regression

```bash
python3 -m pytest tests/test_content_styles.py tests/test_script_postprocessor.py tests/test_apf_import.py -q
```
