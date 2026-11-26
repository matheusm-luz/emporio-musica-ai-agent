---
name: gen-examples
description: Regenerate the example conversations in examples/ by running the real agent through the scripted scenarios. Use after prompt or tool changes that affect the showcased behaviour.
argument-hint: "[provider:model]  default: openai:gpt-6-luna"
disable-model-invocation: true
---

Regenerate `examples/*.md` with the real agent — transcripts must never be written or edited by hand.

1. Model: `$ARGUMENTS`, or `openai:gpt-6-luna` when empty. Check the provider is reachable first
   (see the run-evals skill, step 1).
2. Run `uv run python scripts/run_examples.py --model <provider:model>`. The script freezes the clock
   so dates in the transcripts are reproducible.
3. Review every generated file against `docs/SPEC.md` (scenarios A1–A10 and policies P1–P15):
   correct tool calls, correct prices/dates, PT-BR tone, no invented facts.
4. If a transcript shows wrong behaviour, fix the root cause (prompt, tool, rule) and regenerate —
   never patch the transcript.
5. Summarise: file · scenario · tools called · verdict.
