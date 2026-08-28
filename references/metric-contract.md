# Metric Contract

- Metrics come from validated raw data and deterministic computation.
- Aggregate additive numerators and denominators before calculating ratios.
- Existing definitions in `README.md` and `src/` remain authoritative; do not recalculate in the report layer.
- Do not upgrade proxy fields into real users, repurchase, or profit; do not infer missing metrics as zero.
- Every metric carries dimension, period, definition/unit, and provenance.
