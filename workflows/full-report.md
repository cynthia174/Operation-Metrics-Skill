# Workflow: Full Report

The default route is one continuous chain:

`Excel → Preflight → Metrics → Rules → CapabilityFacts → ModuleContexts → Agent Interaction × 5 → AssembleReport → Semantic Blocks → Word → QA`

After approval, enter `AUTONOMOUS_EXECUTION` and do not ask whether to continue at intermediate nodes. Record each node's input, output, validation, and gaps. A successful node is not overall completion.

After `ModuleContexts`, the host Agent performs the five Prompt stages in order: Channel, Product, Efficiency, GrowthQuality, and Summary. Each Agent stage is a pause/resume checkpoint: the runner records `AWAITING_AGENT_INTERACTION`, the host Agent writes the contracted Markdown output in the current run directory, and the next runner invocation validates that output before changing the stage to `DONE`. Missing output remains `AWAITING_AGENT_INTERACTION`; empty, non-Markdown, or out-of-run outputs are `FAILED`. Only after Summary is `DONE` does the runner execute `AssembleReport`, then the Word renderer and QA stages.

- Reuse the existing implementation and definitions through Rule Result; do not change business logic.
- Keep the existing five-screen report structure.
- Use only validated facts, deterministic metrics, and official Rule Result.
- Treat DOCX as the delivery artifact, not an automatic independent endpoint.
- A partial route is allowed only when the user explicitly requests one step.

## Definition of Done

The workflow may enter `DONE` only when all applicable conditions hold:

- Preflight and approved `/plan` are recorded.
- Normalize, Aggregate, Metrics, Rules, and official Rule Result outputs exist and pass their contracts.
- Report preserves the existing five-screen structure and every formal number/judgment is traceable.
- Fact QA passes; semantic blocks preserve supplied text, order, and roles.
- DOCX is editable and passes applicable DOCX and OOXML QA; any unavailable QA is explicitly marked.
- Data gaps, unsupported rules, `NOT_EXECUTABLE`, and remaining limitations are disclosed in final delivery.
- Final delivery includes the artifact paths, validation status, and no claim beyond the evidence boundary.
