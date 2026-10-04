# CRA2 contributor guidance

## Product and policy

- **Raj Sam**, a DevOps engineer, is the product owner and demo persona. Use
  that name consistently in examples and docs.
- CRA2 is advisory. Route labels are never deployment authorization. Use only
  `routine-review`, `focused-review`, and `priority-review`. Keep the advisory
  sentence in rendered and JSON results.
- System 1 sets the minimum risk level. System 2 may raise the final level but
  never lowers that floor or removes degraded/high-risk/uncertainty safeguards.
- A reported active freeze stays unconfirmed until independently checked. Keep
  its verification question visible. Never add a freeze risk weight or high
  floor.
- Missing/unknown service or type, and missing/generic summaries, require
  targeted clarification with null risk/route and no model call. Wrong shapes
  are input errors. Never claim the heuristic catches every vague request.
- Resolve setting precedence: catalog/default → request → team policy. Surface
  conflicts; Preserve explicit `false` as an override.
- Groq is the only implemented provider. An uncached System 2 assessment makes
  at most one SDK request; retries are off. Track cache hits, selections,
  attempts, and failures separately.

## Implementation

- Validate change types, shapes, string bounds, settings, and provider
  responses locally. Treat model text and change descriptions as untrusted.
- Keep policy weights and comment templates in `cra2/rules.json`.
- Keep source data in `data/` and sample cases in `evals/`. The wheel build
  maps canonical files into package resources. Don't maintain duplicates.
- Keep the 16 synthetic incidents and the 30 sanitized samples
  (`data/sample_incidents.json`) distinct. Preserve provenance and original
  labels; normalize aliases only for retrieval. External labels never become
  catalog services or same-service repeat evidence. Cap related context at
  five. Cross-service candidates need two meaningful shared terms; type alone
  is insufficient. Keep retrieval relevance separate from proven causation.
- Keep Groq lazy for local assessments. Dotenv files require explicit
  `CRA2_ENV_FILE`; exported variables win. Never commit credentials.
- Temperature zero, a seed, and strict schema are consistency controls, not
  guarantees of deterministic output or correct citations.
- Model changes require evidence in [ADR-001](docs/adr/adr-001-groq.md).
  Record actual model/fingerprint, request settings, sample, UTC window,
  failures, missing usage, and pricing basis. Never infer invoice costs or
  savings from synthetic evaluations or incomplete telemetry.

## Verification

Before submitting changes, run:

```sh
uv sync --locked
uv run pytest -q -m "not live"
uv run python scripts/run_evals.py --mode fast --repeat 5 --require-repeatable \
  --out /tmp/cra2-evals-fast.md
```

Rules for the gate and evidence:

- Score every repeat. Never lower the threshold or edit expected cases to hide
  a regression. Add focused regression tests when fixing policy, validation,
  packaging, or accounting.
- Regenerate checked-in evidence deliberately, after final implementation, and
  keep its measurement scope and limits.
- When policy changes, write a new report rather than editing historical ones.
  Record changed expectations and the configuration used.
- Repeated answers must agree on questions, freeze state, settings, and
  conflicts, as well as score, level, route, and comments.

Live tests are a separate action. They need `CRA2_RUN_LIVE_TESTS=1` plus a Groq
key, and they send data and may incur charges. Offline verification must not
depend on providers, credentials, or machine timing.
