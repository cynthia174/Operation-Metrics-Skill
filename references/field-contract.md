# Field Contract

- Declare raw-data file, sheet, date range, and source version.
- Resolve source columns to standard fields; metrics consume standard fields only.
- Missing columns, invalid numeric values, and critical dimension nulls fail explicitly; never silently fill zero.
- Declare grain, keys, complete natural months, and deduplication limits during Preflight.
- This contract does not modify `src/field_mapping.py` or field semantics.
