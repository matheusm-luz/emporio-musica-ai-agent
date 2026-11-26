---
name: run-evals
description: Run the agent eval suite against one or more LLM_MODEL values and summarise pass rates and failures. Use when comparing models or validating a prompt/tool change.
argument-hint: "[provider:model ...]  e.g. ollama:gemma4:12b openai:gpt-6-luna"
disable-model-invocation: true
---

Run the eval suite for each model in `$ARGUMENTS` (default: the `LLM_MODEL` in `.env`).

1. For an `ollama:*` model, check that Ollama is running (`ollama list`) and the model is pulled.
   For an `openai:*` model, check that `OPENAI_API_KEY` is set — never print its value.
2. For each model run: `uv run python evals/run_evals.py --model <provider:model>`.
   The runner freezes the clock (`DEFAULT_NOW` or a case's `now`) and writes `evals/results/<model>.md`.
3. Report a table: model · passed/total · avg latency · failed case IDs.
4. For every failed case, read its transcript in the results file and classify the root cause:
   wrong/missing tool call, wrong fact, forbidden claim, or tone. Propose the smallest fix
   (prompt wording, tool description, or business rule) — do not change the eval to make it pass
   unless the eval itself contradicts `docs/SPEC.md`.
5. If the results change the recommended local model, update the comparison table in README.md.
