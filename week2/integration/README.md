# Week 2 test coverage boundaries

The GitHub `week2` workflow runs the full `week2/tests` suite on Python 3.10 and
3.13. It installs the locked Week 2 dependencies, then runs tests with offline
package/model settings and no live provider authorization. Checkout and Python
setup actions use the same pinned commit references as the repository's other
workflows.

The Slack assessment integration test still exercises real Bolt dispatch, the
Slack engine, admission checks, team preferences, LangGraph, both actual MCP
subprocess tools, historical citation checks and the medium-risk policy floor.
It builds a new SQLite index from the checked-in corpus and runs the real
retrieval pipeline. Only the embedding encoder and provider are deterministic
test doubles. It explicitly fails if the default encoder is requested, so a
developer's ignored model/index cache cannot conceal a CI prerequisite. These
vectors do not establish BGE retrieval quality.

The original real-encoder coverage is preserved as a separately requested local
gate using the same assessment assertions:

```sh
TMPDIR=/tmp uv run --locked --offline --project week2 python -m pytest \
  week2/integration -q
```

This gate verifies checksums of the provisioned model, loads actual FastEmbed/BGE
weights and builds a fresh temporary index before exercising the same Slack/MCP
path. It never downloads a model, never calls Groq or Slack, and **fails** if
weights are missing or invalid. There is no automatic skip. The `/tmp` setting
keeps local test stores inside CRA2's existing permitted temporary-storage root
on macOS as well as Linux.

`test_execution_model.py` additionally covers all three explicit context modes
with both local and injected-reviewer assessments (six cases). It uses the actual
encoder, a fresh corpus index and default MCP subprocess client. Assertions retain
original chunk IDs, global source scope, synthetic/unknown tool provenance, policy
floors, exact action counts and context/trace separation. The injected reviewer
does not provide evidence of real model quality, token usage or cost.

Model provisioning remains a separate explicit setup step described in
`week2/README.md`; model weights and indexes remain ignored local artifacts.
The CI suite is not evidence that this additional real-encoder gate ran. Report
the two results separately, including Python version and test command.
