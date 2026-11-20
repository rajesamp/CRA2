# Guardrail visibility and retrieval evaluation

User requirements: ensure NeMo guardrails are in place; show which conditions
were hit; try Ragas or TruLens. Visibility is **current session only**.

Acceptance:
- Real NeMo 0.24.1 input, host-context and output checks cover chat and the
  incident/rollback report. No model call is required. Check failures fail closed.
- A session activity tab records bounded verdict metadata, never prompts,
  account identities, source contents or private audit records. Blocked admission
  is distinct from a NeMo block, unavailable checks and checks not reached.
- Clearing visible activity cannot clear security cooldowns or durable audit.
  Verified principals cannot read or forge another session's activity.
- Compare Ragas and TruLens on identical offline cases before the decision.
  Pin and independently judge the evidence under the HERMETIC protocol.
- Add a locked, isolated evaluation integration and CI gate with fixed reference
  IDs, negative controls, explicit denominators and failure on unavailable scores.
  Retrieval metrics must not be presented as semantic faithfulness or safety.
- Keep existing contract/adversarial gates. No external judge, deployment,
  account grants or invitations are part of this change.
