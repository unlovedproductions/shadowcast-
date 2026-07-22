# Style × Format Verification

Run after APF enrichment + ShadowCast are up. Check each box when script JSON + badges pass; sample MP4 optional.

**Command helper** (from ShadowCast repo):

```bash
cd ~/shadowcast-/backend
python -m pytest tests/test_content_styles.py tests/test_script_postprocessor.py -q
python video_claim_audit.py --output-dir output --fail-on warn
```

Manual matrix: see `docs/STYLE_RENDERING_CHECKLIST.md` and `tests/STYLE_MATRIX_CHECKLIST.md`.

| Style | Short | Long |
|-------|-------|------|
| honest_review | [x] | [x] |
| elimination | [x] | [x] |
| worth_it_or_waste | [x] | [x] |
| budget_challenge | [x] | [x] |
| vs_battle | [x] | [x] |
| standard | [x] | [x] |

Verified 2026-07-22 (Lilith audit) — automated via `tests/test_style_matrix.py`; manual MP4 optional.
