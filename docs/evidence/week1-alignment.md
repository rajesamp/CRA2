# Week 1 alignment and acceptance record

Date: 2026-09-28. Source: upstream ChangeRiskAdvisor commit `3e52f28ae1f430211d2df6098ab366f38ebdb86e`. [Requirements](../../requirements.md) map the six query intents; [tasks](../../tasks.md) preserve Week 1 task numbers 1–11. Tasks 12–34 remain outside this delivery.

## Deliverables and remaining acceptance

| Task | Implemented artifact / observed evidence | Remaining acceptance |
|---|---|---|
| 1 | [Team record](../team.md), selected isolated Python/FastEmbed/SQLite/Gradio stack | Named owners, individual reading confirmations, team agreement |
| 2 | [Narrative six-pager](../6-pager.md) with six specific sections | Whole-team review and agreement |
| 3 | [Mock release and eight FAQs](../pr-faq.md), including data handling and advisory-only boundary | Whole-team review and agreement |
| 4 | Existing remote repository and feature-branch workflow; append-only root README; [isolated setup guide](../../week1/README.md) and lockfile | Independent teammate fresh-clone/run confirmation |
| 5 | Existing base prompt plus [Week 1 prompt addition](../../week1/prompt.md); [browser transcripts](week1-demo.md) for assessment and refusal | Team/domain review; the transcripts are agent-operated, not a teammate's attestation |
| 6 | Existing 8-service / 10-edge static catalog, 16 synthetic incidents, 30 separately labeled sanitized samples; six services have multiple synthetic incidents | No claim of production freshness or 20 original synthetic records |
| 7 | 46 incident records + 6 derived postmortems + 5 runbooks = 57 source documents; six-intent coverage below | Broader corpus/domain quality review |
| 8 | Real BGE ingestion: 68 chunks and embeddings, 384 dimensions; [counts and fingerprints](week1-retrieval.md) | No operational freshness feed or production scaling claim |
| 9 | Exact checkout-config probe returns relevant history/guidance in the top three; source text and judgments recorded | Broader retrieval-quality measurement remains unproven |
| 10 | Detailed free-text query → real local retrieval → Groq → cited excerpt-based advisory output, with no operational tools | Model attention levels/citation selection remain uncalibrated and human-reviewed |
| 11 | Local Gradio app at port 7861, actual screenshot and response transcript | Authenticated public link, identified team destination, and actual channel post |

The local implementation meets the technical Week 1 demonstration path with the limits above. Week 1 as a team milestone is **partial**, because the upstream definition includes genuine human reviews, a teammate's clone/run, and public sharing/posting. Those events are not inferred from committed files or automated checks.

## Corpus coverage of the six source intents

| Intent | Source coverage | Week 1 behavior |
|---|---|---|
| Checkout config risk | `pm-cx101-checkout-timeout`, `pm-cx102-checkout-retries`, `rb-checkout-config-risk`, canonical CX incidents | Clarify a generic change; detailed mechanism gets retrieved excerpts and optional model attention label |
| Similar incidents | Incident records, derived postmortems, `rb-similar-incidents` | Explicit service/turn context; cite retrieved historical candidates without a new risk rating |
| Freeze/current health | `rb-freeze-health-verification`; existing static snapshot stays separate | Current applicability is unconfirmed; no live lookup claimed |
| Payment dependents | `rb-dependency-verification`; canonical graph remains a static fixture | No inferred edge or claimed graph-tool call; operational lookup deferred |
| Remember high risk | `rb-team-advisory`; existing configured team policy | No memory write or two-session recall claim; static high-risk policy remains authoritative |
| Approve change | `rb-team-advisory`; base and Week 1 prompts | Decline approval/block/merge/deploy, retain human decision reminder |

## Verification

- **151 new offline tests passed**, covering retrieval/index/source integrity, model provisioning, free-text boundaries, Gradio construction/launch, provider validation, credential guards, and excerpt-only rendering. These use fake embeddings/providers except the separately recorded real model/browser demonstrations.
- **402 existing offline tests passed**, with four live tests deselected.
- Existing fast evaluation: **100/100 assessments** met the level/route/citation rubric; 20 cases × five repeats, minimum and mean 10/10. Same decision context across all repeats. No provider calls in that evaluation; it measures the existing core, not the new RAG's semantic quality.
- Static Python checks and Markdown link checks cover the new additions; CI separately runs the core and Week 1 suites on Python 3.10 and 3.13.
- Real model loading/search succeeded with network connections blocked. Ingestion completed without a Groq credential; the index stores source text and local vectors, not authentication data.
- UI file-serving checks returned **403** for `.env` and the repository README. UI configuration returned **200** without a known credential. Exact-key scanning found no matches in scanned working files/reachable Git blobs; the dotenv is ignored, untracked, and mode 0600. This is a scoped check, not a guarantee about unknown or transformed secrets.

Two exploratory live answers contained factual embellishments despite valid citations. The final interface therefore renders canonical source excerpts and fixed questions instead of free-form model prose. Regression tests preserve the two observed failure cases. The model's selected citations and suggested attention level still require judgment; see [demo evidence](week1-demo.md).

## Append-only proof

Baseline: `6adb5664ba974b590a9bd8e4c40242a02d740404`. All **46** original tracked files were checked against Git blob bytes. **45 are byte-identical**. The original README is an exact prefix of its current contents; its only change is a 1,240-byte final Week 1 section. No original code, data, test, lockfile, prompt, or historical report was rewritten, removed, or renamed. All other additions are new paths.

Generated environments, model weights, SQLite stores, and local credentials remain ignored. The optional project does not add runtime dependencies to the core package. Existing prior-week-looking capabilities are retained, but do not count as acceptance of Weeks 2–4.
