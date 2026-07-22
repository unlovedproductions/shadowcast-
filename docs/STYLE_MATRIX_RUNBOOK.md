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
| honest_review | [ ] | [ ] |
| elimination | [ ] | [ ] |
| worth_it_or_waste | [ ] | [ ] |
| budget_challenge | [ ] | [ ] |
| vs_battle | [ ] | [ ] |
| standard | [ ] | [ ] |

Record date + operator when complete.
