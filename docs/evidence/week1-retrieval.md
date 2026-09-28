# Week 1 retrieval evidence

Measured on 2026-09-28T15:19:17.995287+00:00. Operator: coding agent on the local development machine; this is not teammate acceptance. The source base is `6adb5664ba974b590a9bd8e4c40242a02d740404`; only the additive Week 1 implementation is exercised here.

## Ingestion and model identity

- Source documents: **57** — 46 existing incidents, six derived synthetic postmortems, five runbooks.
- Stored chunks / embeddings: **68 / 68**, with **384** float32 dimensions per vector.
- Chunking: up to 160 whitespace-delimited words, 30-word overlap; document title and explicit service accompany each embedding.
- Model: `BAAI/bge-small-en-v1.5`, FastEmbed 0.8.1; local ONNX inference, two threads.
- Corpus SHA256: `d5e8b1fb202a952096c0c089e3485e3fc054d036aec13bf51676859037cb61da`.
- Loaded model/tokenizer fingerprint: `fastembed-artifacts-sha256:6df0bb4a5b7e0d3b1524076116a802509249de2cea5c8b1be7a443d66b7d4338`.
- Qdrant archive SHA256: `3858004b3822f64f940280874b8f2d2dc25b34a4f3eb3cdf617bdceeb21ed9ed`.

The official archive's tokenizer used an unknown-length sentinel that FastEmbed rejected. Setup validates the original archive, then normalizes only `model_max_length` to the model configuration's 512-position limit and verifies the installed artifact checksums. Model weights are unchanged. The installed fingerprint above includes the normalized tokenizer. See [setup code](../../week1/setup_index.py) for the fixed source URL and both checksum sets.

Provisioning is explicit; runtime retrieval uses local files. A fresh-process model load and actual search succeeded with `socket.connect` and `socket.create_connection` blocked, with zero attempted connections. The SQLite index and model weights are ignored local artifacts, not committed data. Queries fail if the corpus/model fingerprint changes or cached citation text differs from the authoritative chunks.

## Upstream task 9 probe

Query: `how risky is this change to checkout-service config?`

Explicit service filter: `checkout-service` plus general guidance. Cosine similarity orders individual chunks; these scores are not risk scores. Judgments below were made by the coding agent against the cited source files, not by an independent domain reviewer.

### 1. `rb-checkout-config-risk#chunk-002` — 0.793765

Source: [week1/corpus/rb-checkout-config-risk.md](../../week1/corpus/rb-checkout-config-risk.md).

**Judgment:** Correct for review guidance: discusses timeout/retry mechanisms, recovery checks, and static-data limits. It is not itself a new incident record and begins in the overlap of a previous paragraph.

Retrieved text:

> 1 to 5 while staging remained at 1, amplifying a payment-gateway slowdown into a retry storm. These incidents are candidates for timeout, retry, and environment-drift changes. Explain the connection to the proposed field; do not cite them as proof that every checkout config change is high-risk. ## Recommended review questions - What failure or latency behavior does the new value permit? - Which callers and dependencies might experience that behavior? - Can the prior configuration and consistent payment/order behavior be restored? - Which named signals reveal retries, timeouts, or incomplete orders? The catalog is a fictional snapshot. Week 1 retrieval does not call a current-health or freeze tool. Label such status as unverified. Cite the relevant incident or source passage for each risk reason, and leave the shipping decision to a human.

### 2. `rb-checkout-config-risk#chunk-001` — 0.768742

Source: [week1/corpus/rb-checkout-config-risk.md](../../week1/corpus/rb-checkout-config-risk.md).

**Judgment:** Correct historical context: explicitly records CX-101 timeout reduction and CX-102 retry/environment-drift facts, with instructions to clarify an unspecified config change.

Retrieved text:

> # Runbook: review a checkout-service config change This is a fictional review guide derived from synthetic historical records. Its checklist is recommended review work, not a report of completed controls or live system state. Sources: [CX-101 and CX-102](../../data/incidents.json), [synthetic catalog snapshot](../../data/checkout_system.json). ## Establish what will change For “How risky is this change to the checkout-service config?”, first obtain the config field, current and proposed values, affected environment, and expected behavior. The question alone does not establish a specific change. Retrieve relevant history while asking for these details; do not invent a before/after state to produce a score. ## Match evidence to the mechanism CX-101 records a payment-call timeout cut from 4 seconds to 400 milliseconds, followed by abandoned authorisations and charges without orders. CX-102 records a production retry increase from 1 to 5 while staging remained at 1, amplifying a payment-gateway slowdown into a retry storm. These incidents are candidates for timeout, retry, and environment-drift changes. Explain the connection to

### 3. `pm-cx101-checkout-timeout#chunk-002` — 0.747570

Source: [week1/corpus/pm-cx101-checkout-timeout.md](../../week1/corpus/pm-cx101-checkout-timeout.md).

**Judgment:** Correct postmortem context for CX-101: recommends checking cancellation/retry/order consistency and restoring the prior timeout. The recorded incident facts are in the preceding chunk of the same document; this chunk alone must not support invented incident details.

Retrieved text:

> - Ask for the current and proposed timeout values and the affected checkout calls. - Check payment-authorisation latency and what happens when a request times out after the external payment operation has started. - Examine whether cancellation, retry, and order creation can leave payment and order state inconsistent. - Ask how to restore the prior setting and how monitoring would detect charges without completed orders. This history is directly relevant to a checkout payment-timeout config change. A shared service or config label alone does not prove that another change has the same failure mechanism. Cite CX-101 and explain the connection before using it as a risk reason. The assessment remains advisory; a human makes the shipping decision.

## Scope and limitations

The probe passes the requested relevance condition: checkout incident/postmortem context appears in the top three. Two chunks come from the same runbook, so this is not a document-diversity result. A single judged query does not establish general retrieval quality or semantic correctness of generated answers. Unknown or ambiguous service identity is clarified instead of inferred. The generic query above produces a clarification in chat; the separate detailed-query demonstration establishes the full assessment round trip.

Reproduce from the repository root after [setup](../../week1/README.md):

```sh
uv run --project week1 python -m week1.setup_index
uv run --project week1 python -c "from week1.retrieval import search; from week1.chat import INDEX; print(search('how risky is this change to checkout-service config?', INDEX, limit=3, service='checkout-service'))"
```
