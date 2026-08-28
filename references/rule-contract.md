# Rule Contract

- Execute only existing Rule Engine rules and declared coverage; do not change thresholds, periods, or meanings.
- Preserve rule identity, `hit`, dimension, period, metrics, threshold, and evidence.
- `hit=false` means the condition did not trigger, not that the business is healthy.
- Missing inputs produce `NOT_EXECUTABLE`, not a fabricated miss.
- Official Rule Result is the only source for formal rule-based conclusions; schema is `docs/rule_result.schema.json`.
