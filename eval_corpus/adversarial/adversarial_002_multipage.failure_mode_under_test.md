# Failure mode: multi-page mixed document

Page 1 is a Quest-style lab report. Page 2 is a discharge summary (not_supported content).

**Expected behaviour:** classifier identifies `lab_report` from the leading page. The second page is ignored for extraction purposes.
