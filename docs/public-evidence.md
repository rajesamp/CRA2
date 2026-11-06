# Public corporate evidence for Change Risk Advisor

CRA2's Week 1 retrieval and Week 2 app now include 13 curated summaries from
first-party corporate sources: 12 incident reports and one staging change plan.
They complement the 16 synthetic incidents, 30 sanitized samples, and Markdown
corpus. They do not extend the service catalog or local incident history used by
the root CLI's deterministic risk rules.

## Source and interpretation contract

The canonical file is `data/public_evidence.json`, included in installed wheels.
`cra2/public_evidence.py` validates its closed versioned schema and creates the
retrieval documents. It preserves company, original service, incident or planned
change date, official source URL, access-check date, facts, recovery and caveats.
Inferred topics and reviewer questions are explicitly separate from reported
facts. The initial schema leaves severity and prospective CRA2 risk null; these
fields are not inferred from outage impact.

Sources include Cloudflare, GitHub, Atlassian, GitLab, AWS, Fastly, Meta, Slack
and Google Cloud. The complete source links appear in the app's **Evidence
sources** tab and in the canonical records. This is a manually reviewed local
snapshot, not a live connector or a mirror of the articles. Public readability
does not establish unrestricted redistribution rights; store concise paraphrases
and original annotations, with attribution and the catalog's rights statement.

The GitLab staging plan is not an outage or a verified successful production
change. Slack's 2021 report says the same-day changes were not the cause: it is a
causal counterexample, not a successful-change label. Cloudflare's February 2026
report has differing onset timestamps; the caveat remains attached. These
outage-heavy sources cannot estimate failure probabilities or calibrate risk.

## Retrieval and semantic state

- Public documents use `public_corporate` provenance and distinct
  `external_incident` / `external_change_plan` kinds. Their service field retains
  the actual corporate service, never `checkout-service` or another CRA2 alias.
- External candidates require at least two meaningful shared terms in reported
  facts, recovery or inferred topic tags before vector ranking. This is a bounded
  relevance heuristic, not proof of causation. At most one external result is
  returned alongside the existing local candidates, within the same top-three
  app limit. There is no guaranteed external match for every query.
- Each bounded public summary stays in one chunk, preserving fact/inference
  labels, attribution and caveats together. Ordinary Markdown chunking is
  unchanged. The existing corpus digest includes these documents; additions or
  corrections invalidate the old index and require rebuilding it. The SQLite
  layout remains compatible and the existing atomic rebuild path is retained.
- Week 2 stores public references as `external_public` evidence, with request
  service and original source service separate. Ingress and context recovery
  validate the exact canonical source and digest. Full, threshold and SAC modes
  retain the same source content. Public evidence is passed as documents and
  cannot become policy, synthetic tool observations or local repeat incidents.
- Sources are untrusted content. Existing advisory wording, policy precedence,
  risk floors, freeze uncertainty, citation checks and provider-call limits
  remain in force. No live health, deployment authorization or causal conclusion
  is supplied by this corpus.

## Validate, rebuild, run

From the repository root, with the existing locked environments and verified
embedding weights available:

```sh
uv run --locked python scripts/validate_public_evidence.py
uv run --locked --project week2 python -m week1.setup_index
uv run --locked --project week2 python -m week2.app --context-mode sac
```

The validator performs no network calls. Index construction uses locally cached
weights; initial provisioning remains the explicit `--download-model` operation
documented in Week 1. Review sources through **Evidence sources**; inspect actual
retrieved context through **Admin → Agent trace**. The demo PIN is not an
authentication mechanism.

Example change request: “Change checkout-service worker routing to withdraw DNS
advertisements during backbone maintenance.” The real-encoder integration check
retrieved Meta's 2021 report as an external analogue; retrieval does not establish
that the proposed change has the same failure mechanism. The cached encoder can
rank local documents above other eligible analogues; this heuristic is not a
measured recall guarantee.

## Adding records

1. Review the original company source and record its URL and access-check date.
   Keep reported facts, recovery, limitations and CRA2 inferences separate.
2. Add a record to `data/public_evidence.json` matching an existing record's
   closed schema and explicit type. Use a unique `public-` ID, the actual company
   and service, and the appropriate event date. Preserve unknown values as null.
   Do not manufacture a SEV, a successful outcome or a CRA2 risk rating.
3. Run the validator above. New publishers require a deliberate reviewed update
   to the publisher host allow-list, not a user-supplied arbitrary fetch URL.
4. Rebuild the index and run focused public-evidence tests plus repository gates.
   Review a relevant query and a nonmatching query for attribution and scope.

The [Google Cloud JSON importer](google-incident-import.md) now provides bounded
fetching, source-specific extraction and deduplicated staging for human review.
Staged records do not enter retrieval until manually curated and validated.
Future work: verified Google/GitLab change outcomes could reduce the outage
selection bias after individual review. Build
an incident-level held-out retrieval benchmark before claiming quality gains;
split by source incident before chunking so retrospective answers do not leak
into their own evaluation inputs. Automatic promotion, an upload UI,
successful-change corpus, persistent action recovery and AgentCore integration
remain outside this increment.
