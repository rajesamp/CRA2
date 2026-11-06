# Google Cloud incident candidates

The importer adds a repeatable discovery step before CRA2's reviewed public
evidence catalog. It reads the official Google Cloud Service Health JSON feed
and writes a local staging file. The app continues to retrieve only the curated
records in `data/public_evidence.json`; staging never changes local incident
history, service catalog, policy, tool results or risk scores.

The [feed](https://status.cloud.google.com/incidents.json) and its
[published schema](https://status.cloud.google.com/incidents.schema.json) supply
stable incident/product/location IDs, source timestamps, product labels, source
severity and narrative updates. Product titles can change. The feed is a partial
window, so disappearance from a later response does not prove deletion,
resolution, or a successful change. Missing end times remain unknown.

## Import

From the repository root:

```sh
uv run --locked python -m cra2.import_google_incidents --fetch \
  --output data/.staging/google-incidents.json
```

`--fetch` explicitly requests the fixed official HTTPS feed. It does not send
CRA2 context to Google or call Groq. Fetching rejects redirects and oversized
responses. There is no arbitrary URL parameter or automatic polling schedule.
For a previously downloaded feed, run the fully offline path:

```sh
uv run --locked python -m cra2.import_google_incidents \
  --input /path/to/google-incidents.json \
  --output data/.staging/google-incidents.json
```

The output is a versioned staging envelope with validated source identity,
original affected products and locations, event/edit timestamps, update counts,
content hashes and a bounded narrative excerpt. The excerpt is untrusted source
text, not a factual paraphrase or an instruction. Full reports are not mirrored
in the staging file. Source severity stays separate from prospective CRA2 risk,
which remains null. Every candidate remains `pending_review`, with causation
`unreviewed` and outcome `unverified`.

Revision hashes detect changes; they are not signatures or proof that the
publisher approved an interpretation. A locally edited staging file is still
unreviewed. Reviewers verify the current source rather than trusting its excerpt
or fingerprint alone.

Repeated imports merge by stable Google incident ID and normalized revision
hash. Identical inputs are idempotent, conflicting duplicate IDs are rejected,
older revisions do not replace newer ones, and records absent from a later
response remain staged. The redundant `most_recent_update` is deduplicated
against the update list. A changed source remains pending review even when its
URL already appears in the curated catalog.

`canonical_record_id` identifies a URL match in the reviewed catalog. Matching
uses the official source URL because CRA2's descriptive IDs differ from Google's
opaque IDs. It prevents a reviewer from accidentally adding a second copy; it
does not certify that the current source revision was reviewed.

Staging files are ignored by Git and omitted from packaged resources. Existing
outputs must validate as staging data before replacement. Validation failures
leave the previous file intact; canonical data files cannot be selected as the
output. The CLI reports counts and protected errors, not source narratives.

## Review and promote

1. Open each candidate's official source link. Read the full report and its
   updates; the excerpt alone is insufficient. Check original product identity,
   event time, edited time and any limits in the source.
2. Decide whether the report contains a useful change-risk mechanism. A heading,
   recent deployment, incident end time or resolved status does not establish
   change causation or a successful deployment. Record unresolved causation or
   outcome explicitly in the caveats. Keep unrelated incidents as clearly
   labeled counterexamples only when they serve a reviewed purpose.
3. For a candidate worth adding, manually create a concise factual paraphrase in
   `data/public_evidence.json` using its existing closed schema. Separate reported
   facts/recovery from inferred topics and questions. Preserve the actual Google
   product name and source URL. Leave severity unextracted and risk unassigned
   under the current curated schema. If `canonical_record_id` is populated,
   review and update that record rather than creating another.
4. Run the existing public-evidence validator, review the diff, and rebuild the
   index:

   ```sh
   uv run --locked python scripts/validate_public_evidence.py
   uv run --locked --project week2 python -m week1.setup_index
   ```

Promotion is an explicit source-content review and repository edit; there is no
`--approve`, automatic model summarization or automatic index refresh in this
increment. See [public evidence maintenance](public-evidence.md) for attribution,
rights and retrieval boundaries. Public access is not an unrestricted reuse
license.

## Evaluation boundary

Committed tests use synthetic narratives with verified feed structure. They
cover edited updates, missing end times, unchanged/older/repeated responses,
source-URL matches and malicious or malformed input. They do not claim better
retrieval recall or a calibrated risk probability. A subsequent relevance
benchmark needs incident-level held-out cases, verified successful-change
outcomes, and incidents unrelated to changes; the retrospective answer must not
appear in its own evaluation input.
