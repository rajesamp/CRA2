# Plan: SAC foundations

Scope: P0/P1 of issue #19, authorized in the implementation request.

## Files that change
- `week2/workflow.py`, `week2/instrumentation.py`: opt-in sanitized observations.
- `scripts/benchmark_sac.py`, `evals/sac-baseline.json`: offline paired baseline.
- `week2/semantic_state.py`: closed bounded state and canonical serialization.
- `week2/compaction.py`: deterministic reference-only reducer.
- `week2/contracts.py`: host context, provenance and transition validation.
- `week2/tests/test_semantic_state.py`, `test_compaction.py`, instrumentation and
  benchmark tests: meaningful positive, failure, replay and compatibility cases.
- `docs/adr-sac.md`, `docs/evidence/sac-baseline.json`,
  `docs/evidence/sac-benchmark.md`: design and measured evidence.
- `week2/README.md`: contributor entry point and scope limits.

## Order of work
1. Inspect safety contracts and run baseline offline suites at `2edc8f6`.
2. Record intent/spec/plan from the already authorized issue scope.
3. Implement optional observation and baseline harness alongside P1 contracts.
4. Run targeted and existing suites, repeatability evals, and baseline harness.
5. Independently review the diff, fix findings, record evidence, push the named
   feature branch and open a draft PR linked to #19 (do not close the issue).

## Risks
Instrumentation must not leak prompts/records or become a control dependency.
Reference-only state must not mistake allow-list membership for factual proof.
Bounds fail closed rather than removing policy/evidence. Provider telemetry can
be missing; report null rather than fabricated zero or cost estimates.

## Proof
Baseline runs compare normalized public output with and without observation.
Reducer tests check stable replay, immutability, service/policy/provenance binding,
malformed/oversized state, unsupported references and credential rejection.
Run root offline tests, Week 2 tests, and five-repeat fast evaluation; preserve
existing expectations. Live calls and P2/P3 comparisons remain outstanding.

## Review refinements
Independent review added policy-namespace exclusion from historical evidence,
matching digests within each tool result, recognized same-service policy refs,
and actual loaded-input digests in benchmark metadata. Reduction requires exactly
one new host ledger entry to prevent stale-state replay. These tighten the planned
authority/provenance and reproducibility checks without extending P0/P1 scope.
