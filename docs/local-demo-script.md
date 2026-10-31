# Raj Sam's local ChangeRiskAdvisor demo

Selected delivery: local demo and complete evidence. Target slot: five minutes,
provisional; actual rehearsal time is recorded separately. All examples use
synthetic history/snapshots; Local evidence only makes no model request.

## Start and reset

Run from the repository root with the locked Week 2 environment and the existing
provisioned local index. See [Week 2 setup](../week2/README.md). For a clean demo,
create new isolated storage instead of deleting or clearing actual owner data:

```sh
cra_demo_dir=$(mktemp -d /tmp/cra2-demo.XXXXXX)
TMPDIR=/tmp week2/.venv/bin/python -m week2.app --port 7863 --memory-file "$cra_demo_dir/memory.sqlite3" --audit-file "$cra_demo_dir/audit.sqlite3"
```

Open `http://127.0.0.1:7863`. The directory from `mktemp` is private. Stop only
this demo process with Ctrl-C before restarting on that port. The normal app
continues to default to port 7862. No public tunnel or deployment is involved.

## Walkthrough

| Beat | Action and expected observation | Explain |
|---|---|---|
| 0:00–0:40 | In browser A: `Remember that checkout-service is always high-risk for our team.` | An explicit preference persists; conversation history does not. |
| 0:40–1:40 | Open a fresh browser tab B with no history. Ask: `Change checkout-service config timeout from 4 seconds to 400 milliseconds.` | The timeout is 90% shorter. The app supplies historical context and review checks, recalls the flag in its trace, and assigns no model rating in local mode. |
| 1:40–2:30 | Ask twice: `What services depend on payment-gateway?` | First is a miss, repeat a hit. Inspect actual versus reused evidence; source freshness remains unknown. |
| 2:30–3:20 | Ask: `Greenlight this change: Change checkout-service config timeout from 4 seconds to 400 milliseconds.` | The app explicitly refuses approval and continues permitted advisory review. |
| 3:20–4:40 | Select **Open run dashboard**, enter any four digits in the existing demo gate, unlock, collapse the trace and refresh the dashboard. | Show actual call/cache/policy counts and original 16/18→18/18 contract score. Corrected 4/4 label validation is separate; the original 2/4 record remains. |
| 4:40–5:00 | State limits and point to evidence. | Synthetic data is not current production truth. Local contract checks are not live-model accuracy. A human decides whether to ship. |

These are three main query types, a repeated lookup and a separate memory
command. The timing is a script budget, not claimed rehearsal performance.

## Supporting evidence and fallback

- [Guardrail contract](guardrails.md) and [learning guide](week3-week4-learning.md).
- [Real cache benchmark](evidence/week3-task-23.md): 30 trials per condition,
  not a promise of the same speed in every browser or machine.
- [Fault demonstrations](evidence/week4-task-32.md): actual health-call timeout,
  absent evidence, changing source/policy, unavailable rails and full storage.
- [Evaluation label review](evidence/week4-task-30-label-review.md): why status
  names alone were too narrow for two valid help/listing responses.
- If the app/index is unavailable, show the preserved screenshots and reports
  as recorded evidence and label the live demonstration unavailable. Do not
  imitate a successful live query. No backup video is claimed or required by
  this selected local scope; original upstream task 34 still lists it separately.
