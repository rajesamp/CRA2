# CLAUDE.md — CRA2 (ChangeRiskAdvisor 2)

## Naming rule (non-negotiable)

- The persona, product owner, and every role owner is **Raj Sam** (DevOps engineer).
- Use "Raj Sam" in all docs, prompts, datasets, transcripts, demo scripts, and UI copy.
  Do not use any other persona or person name.

## Engineering rules

- Groq is the only model provider. System 2 makes exactly one call per assessment.
- Keep the determinism settings: temperature 0, fixed seed, pinned model, strict JSON
  schema. Change `CRA2_MODEL` only with an eval run recorded in `docs/adr/adr-001-groq.md`.
- Advisory only: CRA2 recommends a route; it never approves, blocks, merges, or deploys.
- Keep `cra2/` small. Risk rules and comment wording belong in `cra2/rules.json`, not code.
- Before pushing: `uv run pytest -q` and `uv run python scripts/run_evals.py --mode fast`.
