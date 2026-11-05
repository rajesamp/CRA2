# Task 28 — retained local baseline

2026-10-31. [Timestamped per-case baseline](week4-task-28-baseline.json):
**16/18 cases passed**, zero provider attempts. The runner
returned exit code 1 because two cases failed; it did not hide the failed gate.
Baseline code revision: `17bcfcf4775aca5456bc83f4f7e8183169f210a0`. Case/scorer/index/corpus/policy/tool
identities are in the report. Reserved cases have not been executed.

This baseline is after Week 3, before Week 4 quality fixes. The six core
contracts passed, including the known relevant CX-101 source in the checkout
top three. The two failures concern approval paraphrases; task 29 analyzes
them before a code fix is selected. The report is retained unchanged.

Learning: a useful baseline includes failures and individual checks. A total
score cannot reveal whether the missed contract was routing, evidence support
or approval refusal. These are local contract cases, not live-model quality.
