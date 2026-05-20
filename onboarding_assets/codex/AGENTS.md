## Shellbrain

You have a persistent memory system called Shellbrain. This section exists to make you remember to use it at the right moments.

### The Core Habit

As you work, maintain a mental summary of your current subproblem as:

`goal | surface | obstacle | hypothesis`

When that tuple changes materially, or you hit a boundary state, pause and say one `SB:` line out loud by actually generating it as output. This keeps Shellbrain in your local attention so you can decide whether recall would help.

Boundary states:

- The goal, surface, obstacle, or hypothesis changed.
- The same approach failed twice.
- An error is repeating.
- You are about to make an evidence-bearing decision.
- You are switching files, subsystems, or implementation strategy.
- You are closing out a task.

### What To Say

If prior context might help:

`SB: recall | <goal> | <surface> | <obstacle> | <hypothesis-or-trigger>`

Then call Shellbrain recall:

```bash
shellbrain recall --json '{"query":"<targeted question>","current_problem":{"goal":"<goal>","surface":"<surface>","obstacle":"<obstacle>","hypothesis":"<hypothesis or none yet>"}}'
```

If the tuple has not changed and there is no new evidence, failure, or uncertainty:

`SB: skip | same signature | <one-line reason>`

Then continue. Do not call recall reflexively.

### Worker Boundary

As the working agent, use `shellbrain recall` for normal task context. Use `shellbrain teach` only when the user explicitly asks you to store or teach Shellbrain something.

Do not call `shellbrain read`, `shellbrain events`, `shellbrain memory`, `shellbrain concept`, or `shellbrain scenario`.

Shellbrain's internal agents handle raw retrieval, synthesis, memory writing, concept updates, scenario recording, and teach consolidation.

### Reference

Use the installed `shellbrain` skill for the detailed recall workflow.
