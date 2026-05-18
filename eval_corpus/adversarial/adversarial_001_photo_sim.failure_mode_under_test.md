# Failure mode: photo-of-paper

This PDF is image-only (no selectable text layer). Textract's primary table-extraction path will fail; the pipeline must fall back to the vision-LLM path.

**Expected behaviour:** classified as `lab_report`; extraction via vision-LLM fallback.
