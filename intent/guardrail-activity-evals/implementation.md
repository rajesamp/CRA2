# Implementation and evidence

The Guardrail activity tab stores a maximum of 100 requests in server-owned
Gradio session state. A lock preserves concurrent chat/report updates. Verified
principal session namespacing remains the authenticated access boundary. Only
closed-vocabulary verdict metadata reaches the HTML view; there is no audit-log
reader, prompt text, account identity, arbitrary classifier output or source prose.
Clear affects this view only; it does not clear the abuse gate or private audit.

Existing chat already invoked NeMo 0.24.1. The incident/rollback callback now
runs the same real input, host-context and output checks after admission. Source
instructions and approval language suppress the report. Initialization/check
failure provides no readiness conclusion. Input serialization/credential errors
now emit an explicit unavailable verdict. The panel distinguishes admission
blocks, actual NeMo blocks, unavailable checks, and stages not reached/required.

The NeMo configuration has no LLM. Its custom actions enforce bounded protected
action, evidence structure/injection-pattern, and advisory/approval contracts.
This is **not** a general semantic jailbreak detector or a proof of correctness.
Context is checked by the host through an input rail, not NeMo-managed retrieval.
Existing tool schema/inventory checks, admission classifier, IAP isolation,
provider restrictions and audit controls remain separate layers.

TruLens Feedback 2.16.0 is isolated under `evaluation/`; it is excluded from the
container build context. CI's Python 3.13 leg installs its lock, tests the metric
failure paths, collects real BGE retrieval IDs, and evaluates six frozen cases.
The Python 3.10/3.13 application gates remain intact. No semantic LLM judge is
configured; attempting one or internet socket/DNS operations fails evaluation.

Local validation before publication:
- 459 application tests passed on Python 3.13.
- 14 evaluator tests passed; seven scorer controls passed.
- 18 development/validation and four reserved security contracts passed.
- Nine fault checks and seven existing contract-scorer controls passed.
- Real BGE retrieval: six cases; mean document precision and recall each 0.8333.
  Every case met the predeclared regression floors. No observed egress or
  provider attempts. These small same-author labels are not held-out quality gold.
- Real mounted app: two verified users with the same browser session ID retain
  independent activity, browser-forged state is ignored, and clearing one does
  not clear the other. Concurrency, bounded history and private-metadata tests pass.
- Browser walkthrough: a benign incident report recorded admission and three
  actual NeMo passes; a protected-action chat request recorded admission block
  and all three NeMo stages as not reached. Screenshot retained privately.

The immutable framework manifest and fresh judge output are adjacent. The
validated level is **suitable**, selecting TruLens for this pilot. A quality
winner is not established. The smallest separating test is both adapters on
the same frozen CRA2 cases with identical failure rules. The shared six API
fixtures alone do not establish broader superiority.

This work is a draft release. No Cloud Run rollout, new access grant or user
invitation is included. A release still needs its normal CI/image/security gates
and owner acceptance.
