# Inventory schema incident: a caller still used the old column name

Document type: synthetic postmortem derived from a historical fixture. This is a fictional training example, not current production evidence.

Source: [canonical synthetic incidents](../../data/incidents.json), incident **CX-109**.
Service: **inventory-service**. Date: **2026-01-22**. Change type: **Schema migration**. Severity: **SEV2**.

## Recorded facts

A column was renamed while order-service still read the old name. Stock lookups from order-service failed for **15 minutes**.

The fixture does not name the column or database, provide a complete caller inventory, or describe recovery. The reported caller relationship is specific to this historical incident and does not prove a current dependency graph.

## Suggested checks for a proposed change

These are review recommendations, not additional incident facts:

- Request the current and proposed column names and the known callers affected by the schema change.
- Check whether old and new callers can coexist during a staged migration.
- Review the sequencing of schema and caller changes, including how compatibility will be verified.
- Ask what monitoring detects failed stock lookups and whether the rollback plan restores caller compatibility.

CX-109 is relevant when a change may remove a schema contract before its consumers have migrated. Do not invent additional downstream services or assume that a similarly named service is the historical caller. Use a labeled catalog snapshot only for snapshot claims; current dependency verification is separate work. The assistant provides advice, not a shipping decision.
