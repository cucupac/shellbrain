## Shellbrain

You have a persistent memory system called Shellbrain. This section teaches you a habit for using it well.

### The core habit

As you work, maintain a mental summary of your current subproblem as a tuple: `goal | surface | obstacle | hypothesis`.

Whenever that tuple changes materially, or you hit a boundary state, pause and say one `SB:` line out loud by actually generating it as output. This forces Shellbrain back into your local context so you can make a real decision about whether to use it.

Boundary states:

- The goal, surface, obstacle, or hypothesis just changed.
- The same approach failed twice.
- An error is repeating.
- You are about to `create` or `update` a Shellbrain memory with evidence.
- You are closing out a task.

### What to say at the pause

If prior memory might help right now:

`SB: read | <goal> | <surface> | <obstacle> | <hypothesis-or-trigger>`

Then actually call the Shellbrain CLI to read.

If the tuple has not meaningfully changed and there is no new evidence or failure:

`SB: skip | same signature | <one-line reason>`

Then move on. Do not reread just because you can. A reread is a decision, not a reflex. Skip it when there is no new failed attempt, no new evidence, and no changed hypothesis.

### Before writing to Shellbrain

Run `shellbrain events` before any evidence-bearing `create` or `update`. This is mandatory.

### At closeout

When work is solved, write durable memories (`problem`, `failed_tactic`, `solution`, `fact`, `preference`, or `change`) and run `utility_vote` updates.

### Reference

Use the installed `shellbrain-session-start` skill for the exact query and writeback workflow.
