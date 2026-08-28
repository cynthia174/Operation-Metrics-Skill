# Workflow: Preflight

Preflight confirms raw data, fields, time range, mappings, and rule coverage before any formal calculation or generation.

1. `INIT → PREFLIGHT`: register raw data, file/sheet, version, goal, and deliverables.
2. Check readability, rows, time range, complete natural months, required fields, null/type errors, and duplicate risks.
3. Resolve source columns to standard business fields without changing the mapping.
4. List executable rules, missing inputs, and coverage limits.
5. Output `/plan` with stages, inputs/outputs, coverage, gaps, risks, and deliverables.
6. Enter `AWAITING_PLAN_APPROVAL` and stop.

If input is incomplete, output a blocked `/plan`; do not generate formal numbers or conclusions.
