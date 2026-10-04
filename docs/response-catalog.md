# Editing the response catalog

Edit [`week1/responses.json`](../week1/responses.json) to change fixed answer
text, capability labels, dataset field labels, or exact documentation FAQs.
Do not edit `chat.py` for these changes. The file reloads on every request, so
JSON-only edits need no restart and no index rebuild.

## Sections

| Section | Purpose |
|---|---|
| `version` | Schema version; keep `1` |
| `messages` | Answer and clarification templates; keep keys and placeholders |
| `capabilities` | Ordered labels for capability questions; describe only implemented behavior |
| `field_labels` | Display names for canonical incident fields; keep the four keys |
| `faq` | Documentation answers with an ID and exact question aliases |

## Add a FAQ entry

Append an object inside the `faq` array:

```json
{
  "id": "sample-data",
  "questions": [
    "Does CRA2 use sample data?",
    "Where does CRA2 get its incident examples?"
  ],
  "answer": "CRA2 uses synthetic incidents and sanitized sample records."
}
```

Aliases ignore case, repeated whitespace, and terminal `.?!`. They match the
whole question. They are exact strings, not regular expressions or substring
triggers. Add one alias per phrasing you want to support. Keep IDs and
normalized aliases unique.

## Precedence

A supported task beats a FAQ. Help, dataset browsing, change assessment,
history comparison, clarification, and the advisory boundary all take priority.
A FAQ alias for `Just approve this change for me` cannot replace the
advisory-boundary handler. Edit `messages.help` for the general help answer;
adding that question to `faq` does not override its handler.

Unmatched unrelated questions keep the fixed out-of-scope response. FAQs ignore
prior service history and make no retrieval or provider call. Code appends the
human-decision reminder.

## Templates and facts

| Message key | Required placeholder |
|---|---|
| `unknown_dataset_service` | `{services}` |
| `distinct_title_count`, `incident_count` | `{count}` |
| `specific_change` | `{service}` |
| `risk_indication` | `{level}` |
| `high_risk_policy`, `freeze_policy` | `{source}` |
| `capability_limit` | `{total}` |

Other messages have no placeholders. The loader rejects format conversions,
format specifications, attribute or index access, and unknown placeholders.

Incident counts, details, citations, and scenario-title source hashes come
from canonical records. Do not copy dynamic incident answers or invented risk
assessments into FAQs. Curated incident titles live in
`week1/scenario_titles.json` under their existing source-hash checks.

## Validation limits

The catalog must fit in 64 KiB. Text values cap at 4,000 characters, capability
lists hold 1–20 labels, and `faq` holds up to 50 entries with 1–20 aliases each.

A generic failure occurs before retrieval or inference when the catalog has
missing keys, invalid types, duplicate JSON keys or aliases, invalid
placeholders, control characters, or configured Groq/UI credentials. The UI
hides raw error text.

FAQ answers are conservatively rejected when they contain known decision
phrases or explicit risk-label syntax. That is output hygiene, not proof the
text is factual or safe.

## Review expectations

This is trusted application content maintained through code review. The
running conversational agent neither writes the file nor learns answers from
chat. A development agent may edit the JSON and submit it for review.

When adding entries, review the claim and its scope. A registered alias becomes
a supported documentation question. New operational behavior or routing rules
still require code and tests.

Validate without a provider call:

```sh
uv run --project week1 python -c 'from week1.responses import load; load(); print("Response catalog valid")'
uv run --project week1 python -m pytest week1/tests -q
```

## File responsibilities

| File | Responsibility |
|---|---|
| `week1/chat.py` | Request flow, scope and service handling, policy enforcement, provider and evidence validation |
| `week1/answers.py` | Dataset projections and evidence lists from canonical facts |
| `week1/responses.py` | Catalog validation, safe template rendering, FAQ lookup, shared clarification and credential helpers |
| `week1/responses.json` | Editable response content and FAQ aliases |