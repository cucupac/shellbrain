---
name: shellbrain-usage-review
description: Review Shellbrain usage measurements across repositories and identify useful product follow-up.
---

# Shellbrain Usage Review

Run `shellbrain admin analytics --days 2`.

The JSON report contains observed counts, command latency, empty retrieval results,
sync totals, and grouped errors with sample record IDs. It does not assign health
scores or product priorities.

Use the measurements and supporting records to explain what works, what fails,
and which changes would help. Distinguish your interpretation from measured facts.
A successful call does not establish that the memory helped solve a task.
Do not infer missing recall from counts alone without checking task context.
