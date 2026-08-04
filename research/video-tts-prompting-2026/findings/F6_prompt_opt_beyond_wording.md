# F6 — Eval-gated schema/metrics beat more prompt prose; DSPy only with metrics

**Status:** CONFIRMED
**Sources:** 13, 14, 16

## Thesis
Strict structured outputs + eval gates + few-shot only when parse failures cluster. DSPy/MIPROv2 helps iff numeric metric + trainset exist. Manual prompt rewriting without live eval regresses.

## ShadowCast delta
Already has live 16/16 baseline and prompt optimizer. Priority: keep eval gate; consider constrained decoding on OpenAI path; prune few-shots until failures appear; do not DSPy-rewrite working prompts for credit theater.
