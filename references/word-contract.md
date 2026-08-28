# Word Contract

- DOCX is a delivery artifact in the full workflow, not an automatic independent endpoint.
- Preserve existing parameters: Arial; body/table 11 pt; heading levels 18/16/15 pt; title 26 pt, unless the user explicitly supplies an update.
- Keep editable text and tables; do not embed whole pages as images.
- If semantic blocks are supplied upstream, preserve text, order, and semantic role; adjust only renderer/resources/QA.
- Record DOCX QA and OOXML QA separately; never claim visual QA when it was not run.
