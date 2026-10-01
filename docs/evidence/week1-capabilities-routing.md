# Week 1 capabilities routing regression

Date: 2026-09-30 (America/Chicago). Baseline: `bca88522a8d176811f2805da16b9c0b3b15d9fe8`.

## Observed failure

The user reported: `I am a mentor and wants to understand top 5 capabilities of this agent, list me out`. The supplied screenshot shows a catalog-service clarification and unrelated incident evidence. The reported spelling `capabilties` is also covered.

A baseline replay with an injected empty retriever returned `needs_clarification` and made one retrieval call. The help parser recognized narrow phrases naming CRA2, but did not recognize capabilities questions about “this agent.” The request fell through to the change-assessment path. Groq did not generate the incorrect clarification.

## Change

The [router](../../week1/routing.py) recognizes capabilities/features questions referring to CRA2, this agent/assistant, or you/your, plus common onboarding forms. The [chat handler](../../week1/chat.py) renders up to five labels from implemented behavior:

1. Browse incident titles and recorded details
2. Count incident records and distinct scenario titles
3. Find historical incidents relevant to a proposed change
4. Provide cited change-risk advice and review questions
5. Surface configured team risk settings and unconfirmed freeze reports

Help is resolved before service inheritance or retrieval. Capabilities answers contain only the requested list. Requests exceeding the five implemented groups clarify rather than invent features. Mixed requests clarify. No live health/dependency lookup, persistent memory, approval, or execution capability is claimed.

## Verification

- **328 Week 1 tests passed**, including **66 additional regressions** for capabilities phrasing/spelling, both UI modes, three history contexts, requested list length, mixed requests, basic onboarding, the actual UI wrapper, and a valid service-change request mentioning worker functions.
- **402 core tests passed**, with four live tests deselected.
- Required fast evaluation passed **100/100** assessments, 20 cases × five repeats; minimum rubric score 10/10, same decision context for every case, zero provider attempts. UTC evaluation window: `2026-10-01T00:11:35.650319+00:00` to `2026-10-01T00:11:35.709312+00:00`.
- Capabilities/help regressions fail if retrieval or Groq is called. The five-label response is identical across empty, checkout, and auth histories. Existing listing, scope, count, assessment, and advisory-boundary regressions continue to pass.
- Capability terms must refer to the agent. Merely mentioning “you” and service “functions” in the same request does not make it a help request.
- Locked environment synchronization, Ruff formatting/static checks, and Git whitespace checks passed.
- Exact configured-secret checks found zero matches in 89 tracked/non-ignored working-tree files and the private UI log; a detection canary passed. The ignored `.env` and UI log both have `0600` permissions. This check covers the configured secret values in those files, not every possible leak destination.

These are bounded regression results, not unrestricted language accuracy. The earlier browser URL-policy rejection prevents an automated new screen check; this update is verified through the real UI wrapper and offline app tests. Historical screenshots and close-out evidence do not establish this revision's rendered appearance.
