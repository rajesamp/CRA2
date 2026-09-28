# Order schema incident: index creation blocked writes

Document type: synthetic postmortem derived from a historical fixture. This is a fictional training example, not current production evidence.

Source: [canonical synthetic incidents](../../data/incidents.json), incident **CX-107**.
Service: **order-service**. Date: **2025-12-05**. Change type: **Schema migration**. Severity: **SEV2**.

## Recorded facts

An index build on the orders table ran without the online option. It locked writes for **6 minutes at peak**.

The fixture does not identify the database product, SQL statement, table size, or the eventual completion or rollback procedure. The six-minute write lock is the only recorded duration; it is not a forecast for a new migration.

## Suggested checks for a proposed change

These are review recommendations, not additional incident facts:

- Ask which table and index change is proposed and which database/version will execute it.
- Verify the operation's actual locking behavior, including whether an online option is available and configured.
- Review the expected write workload, observation plan, and a procedure for handling excessive blocking.
- Examine reversal or interruption constraints rather than assuming an application redeploy reverses a database operation.

CX-107 supports review of a migration whose execution can lock order writes. It does not establish a risk level for every schema change. Cite the recorded mechanism and distinguish verified migration details from questions still needing an answer. This is advisory evidence for a human reviewer.
