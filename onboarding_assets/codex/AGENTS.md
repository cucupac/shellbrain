## Shellbrain

Use Shellbrain for targeted recall during agent work.

Keep this tuple in mind:

`goal | surface | obstacle | hypothesis`

Emit one `SB:` line when the tuple changes or you hit a boundary state:

- goal, surface, obstacle, or hypothesis changed
- same approach failed twice
- an error repeats
- you are about to make an evidence-bearing decision
- you switch files, subsystems, or strategy
- you are closing out

If prior context may help:

`SB: recall | <goal> | <surface> | <obstacle> | <hypothesis-or-trigger>`

Then run:

```bash
shellbrain recall --json '{"query":"<targeted question>","current_problem":{"goal":"<goal>","surface":"<surface>","obstacle":"<obstacle>","hypothesis":"<hypothesis or none yet>"}}'
```

If recall would not help:

`SB: skip | same signature | <one-line reason>`

Then continue. Do not call recall reflexively.

Use `shellbrain recall` for normal task context. Use `shellbrain teach` only when the user explicitly asks you to store or teach Shellbrain something.

If you changed any files since your last user-facing response, run `shellbrain snapshot` exactly once after validation and immediately before your next user-facing response. Do this on every response cycle where files changed; skip only when no files changed.

Do not call `shellbrain read`, `shellbrain events`, `shellbrain memory`, `shellbrain concept`, or `shellbrain scenario`.

Use the installed `shellbrain` skill for the detailed recall workflow.
