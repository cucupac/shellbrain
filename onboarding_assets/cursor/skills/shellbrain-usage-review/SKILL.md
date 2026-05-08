---
name: shellbrain-usage-review
description: Use when a reviewer agent needs one fast cross-repo picture of how agents are using Shellbrain, where the product is working, where it is failing, and which expected capabilities are being skipped.
---

# Shellbrain Usage Review

Run the canonical cross-repo analytics report and synthesize it for review.

## Primary Command

```bash
shellbrain admin analytics --days 2
```

## What To Extract

- where Shellbrain is working well
- where it is failing
- what is failing and why
- where agents are skipping expected capabilities, especially `utility_vote`
- the top priorities that should drive product follow-up

## Operating Rules

- treat the JSON report as the source of truth
- do not reconstruct the report with ad hoc SQL unless the command is broken
- summarize the strongest wins, the most important failures, and the highest-priority capability gaps first
- use `repo_rollups` only as secondary supporting context
