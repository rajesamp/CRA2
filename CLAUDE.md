# CRA2 contributor guidance

## Product and policy

- The product owner and demonstration persona is **Raj Sam**, a DevOps engineer.
  Keep that name consistent in synthetic examples and documentation.
- CRA2 is advisory. Route labels must never become deployment authorization.
  Keep the advisory sentence in both rendered and JSON results.
- System 1 establishes a minimum risk level. System 2 may raise the final level
  but cannot lower that floor, remove freeze/degraded safeguards, or place an
  uncertain change into the low route.
- Groq is the only implemented provider. An uncached System 2 assessment makes
  at most one SDK request attempt; automatic retries are disabled. Distinguish
  cache hits, selected requests, attempted requests, and failed requests.

## Implementation rules

- Validate change types, shapes, bounded string fields, settings, and provider
  responses locally. Treat model text and change descriptions as untrusted data.
- Keep policy weights and comment templates in `cra2/rules.json`.
- Keep source data in `data/` and sample cases in `evals/`. The wheel build maps
  those canonical files into package resources; do not maintain duplicate copies.
- Keep the 16 original synthetic incidents distinct from the 30 sanitized
  user-provided samples in `data/sample_incidents.json`. Preserve source
  provenance and original service/type labels; normalize aliases only for
  retrieval. External service labels must not become invented catalog services
  or same-service repeat-incident evidence. Related context stays capped at five.
- Preserve lazy Groq loading for local assessments. Dotenv files require explicit
  `CRA2_ENV_FILE`; exported variables take precedence. Never commit credentials.
- Temperature zero, a seed, and strict schema are consistency controls, not a
  guarantee of deterministic model output or semantically correct citations.
- Model changes require evidence in [ADR-001](docs/adr/adr-001-groq.md). Record
  the actual model/fingerprint, request settings, sample, UTC window, failures,
  missing usage, and pricing basis. Never claim invoice costs or savings from
  synthetic evaluations or incomplete telemetry.

## Verification

Before submitting changes, run:

```sh
uv sync --locked
uv run pytest -q -m "not live"
uv run python scripts/run_evals.py --mode fast --repeat 5 --require-repeatable \
  --out /tmp/cra2-evals-fast.md
```

The evaluation gate scores every repeat. Do not lower its threshold or update
expected cases merely to hide a regression. Add focused regression tests when
fixing policy, validation, packaging, or accounting behavior. Regenerate checked-in
evidence deliberately after the final implementation, retaining measurement
scope and limitations.

Live tests are a separate action: both `CRA2_RUN_LIVE_TESTS=1` and a Groq key are
required. They send data and may incur charges. Normal offline verification must
not depend on provider availability, credentials, or timing guarantees from a
particular machine.
