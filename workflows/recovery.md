# Workflow: Recovery

Use when reading, field resolution, rule coverage, a node, or QA fails.

- Preserve outputs and evidence from passed nodes; do not rewrite business logic.
- Restart at the first failed node and revalidate downstream outputs.
- Never fill data gaps by inference; use `NOT_EXECUTABLE` with impact and required input.
- If scope, mapping, definition, or plan changes, return to `PREFLIGHT`, issue a new `/plan`, and wait for approval.
- Ordinary fixes after approval remain autonomous; only a changed objective or scope requires new approval.
