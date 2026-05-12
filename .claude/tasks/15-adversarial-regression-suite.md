# Task 15 — Adversarial regression suite

## Context

Per architecture §7.2 Layer 4 and roadmap §4 exit criterion #5, the capstone must demonstrate that 20+ adversarial prompts targeting clinical-advice elicitation all return refusals. This task turns `eval_corpus/adversarial_prompts.json` (from task 03) into a real pytest-driven regression suite that runs on every prompt change.

## Dependencies

- Task 03 (adversarial prompts JSON)
- Task 12 (Observation Generator + banned-phrase list)
- Task 13 (Summary Generator + Mode A)

## In scope

`tests/adversarial/`:

- `test_adversarial.py` — pytest module that:
  - Loads `eval_corpus/adversarial_prompts.json`.
  - Parametrizes one test per prompt.
  - For each, fires the prompt at the targeted generator (Observation / Summary / NLQ-stub).
  - Asserts: response either refuses outright OR contains no banned phrases AND passes Layer 3.
- `make adversarial` — Makefile target that runs `pytest tests/adversarial -q --tb=short`.
- `eval_corpus/adversarial_results.md` — generated report listing each prompt + observed response + pass/fail. Regenerated each run.

Banned-phrase list comes from `src/gateway/guardrails/banned_phrases.py` (task 12). Adversarial suite imports it directly so the lists never diverge.

**Planted hallucination test:** one additional test that injects a known-bad citation into a fixture summary and asserts Mode A rejects it. This is the proof that roadmap §4 exit criterion #6 ("citation verifier catches at least one real hallucination") is satisfied.

## Out of scope (deferred)

- LLM-as-judge re-scoring (v1).
- A/B prompt testing in production (Scale).
- Red-team exercises (Scale).

## Files to create

- `tests/adversarial/__init__.py`
- `tests/adversarial/test_adversarial.py`
- `tests/adversarial/test_planted_hallucination.py`
- `eval_corpus/adversarial_results.md` (output)
- Update `Makefile` to add `adversarial` target.

## Architecture references

- `docs/Vitalog_architecture.md` §7.2 Layer 4 — adversarial test suite
- `docs/Vitalog_architecture.md` §11 capstone scope — 20+ adversarial prompts
- `docs/Vitalog_PRD_v2.md` §Testing & Measurement
- `docs/vitalog_roadmap.md` §4 exit criteria #5 and #6

## Step-by-step

1. Confirm `eval_corpus/adversarial_prompts.json` has ≥20 entries spanning all 3 targets.
2. Write parametrized pytest in `test_adversarial.py`.
3. Implement results-report writer (markdown table per run).
4. Implement planted-hallucination test against a Mode A fixture.
5. Wire `make adversarial`.
6. Run end-to-end; record pass count in `EVAL_RESULTS.md`.

## Acceptance criteria

- [ ] `make adversarial` runs all 20+ prompts and prints pass/fail per prompt.
- [ ] All prompts return refusals or banned-phrase-free responses.
- [ ] Planted-hallucination test passes (Mode A rejects the doctored summary).
- [ ] `adversarial_results.md` is regenerated each run.
- [ ] Banned-phrase list comes from the same module Layer 3 uses (no duplicate list).

## Verification

- `make adversarial`
- Inspect `eval_corpus/adversarial_results.md` — at least 20 rows, all PASS.
- `git diff` shows no edits to `banned_phrases.py` from test code.
