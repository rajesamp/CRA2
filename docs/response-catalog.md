# Editing Week 1 answers

Edit [`week1/responses.json`](../week1/responses.json) to change fixed answer text, capability labels, dataset field labels, or exact documentation FAQs. You do not need to edit `chat.py` for these changes. The file is read on each request; after the refactored app has started, later JSON-only edits need no restart or index rebuild.

## Catalog sections

| Section | Purpose |
| --- | --- |
| `version` | Schema version; keep `1` |
| `messages` | Existing answer and clarification templates; retain their keys and required placeholders |
| `capabilities` | Ordered labels returned by capabilities questions; only describe implemented behavior |
| `field_labels` | Display names for canonical incident fields; keep the four existing keys |
| `faq` | Documentation answers with an ID and one or more exact question aliases |

For example, append this object inside the `faq` array:

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

Aliases ignore case, repeated whitespace, and terminal `.?!` punctuation. They match the whole question. They are not regular expressions or substring triggers. Add an alias for each additional phrasing you want to support. Keep IDs and normalized aliases unique.

An existing supported task takes precedence over a FAQ, including help, dataset browsing, change assessment, history comparison, clarification, and advisory/Week 2 boundaries. For example, a FAQ alias for `Just approve this change for me` cannot replace the advisory-boundary handler. Edit `messages.help` for the existing general help answer; adding that same question to `faq` does not override its handler. Unmatched unrelated questions retain the repository response. FAQs ignore previous service history and make no retrieval or provider call. The fixed human-decision reminder is appended by code.

## Templates and facts

| Message key | Required placeholder |
| --- | --- |
| `unknown_dataset_service` | `{services}` |
| `distinct_title_count`, `incident_count` | `{count}` |
| `specific_change` | `{service}` |
| `risk_indication` | `{level}` |
| `high_risk_policy`, `freeze_policy` | `{source}` |
| `capability_limit` | `{total}` |

Other messages have no placeholders. Formatting conversions, format specifications, attribute/index access, and unknown placeholders are rejected. Incident counts, details, citations, and scenario-title source hashes continue to come from canonical records. Do not copy dynamic incident answers or invented risk assessments into FAQs. Curated incident titles remain in `week1/scenario_titles.json`, with their existing source-hash checks.

## Validation and review

The catalog must fit within 64 KiB. Text values are limited to 4,000 characters, capability lists to 1–20 labels, FAQs to 50 entries, and each FAQ to 1–20 aliases. Missing keys, invalid types, duplicate JSON keys/aliases, invalid placeholders, control characters, and configured Groq/UI credentials cause a generic failure before retrieval or inference. The UI hides raw error text. Known decision phrases and explicit risk-label syntax in FAQ answers are conservatively rejected; this is output hygiene, not proof that arbitrary text is factual or safe.

This is trusted application content maintained through code review. The running conversational agent does not write the file or learn new answers from chat. A development agent can edit the JSON and submit the change for review. Review claims and scope when adding entries; a registered alias becomes a supported documentation question. New operational behavior or new routing rules still require code and tests.

Save valid JSON before sending the next request. Validate without a provider call:

```sh
uv run --project week1 python -c 'from week1.responses import load; load(); print("Response catalog valid")'
uv run --project week1 python -m pytest week1/tests -q
```

## File responsibilities

- `week1/chat.py`: request flow, scope and service handling, policy enforcement, provider/evidence validation.
- `week1/answers.py`: dataset projections and concise evidence lists from canonical facts.
- `week1/responses.py`: catalog validation, safe template rendering, exact FAQ lookup, and shared clarification/credential helpers.
- `week1/responses.json`: editable response content and FAQ aliases.

No Week 2 tool or memory feature is implemented by this extraction.
