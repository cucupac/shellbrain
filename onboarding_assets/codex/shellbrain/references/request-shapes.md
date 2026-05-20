# Shellbrain Recall Request Shape

The normal working-agent CLI interface is `shellbrain recall`.

Use it when prior context may help the current problem. Use `shellbrain teach` only when the user explicitly asks you to store or teach Shellbrain something. Do not call internal Shellbrain commands directly.

## Recall

`current_problem` is required. All four fields must be non-empty strings:

- `goal`
- `surface`
- `obstacle`
- `hypothesis`

If you do not have a hypothesis yet, use `"none yet"`.

Minimal shape:

```bash
shellbrain recall --json '{"query":"<targeted question>","current_problem":{"goal":"<goal>","surface":"<surface>","obstacle":"<obstacle>","hypothesis":"<hypothesis or none yet>"}}'
```

Concrete example:

```bash
shellbrain recall --json '{"query":"Have we seen this failure mode or subsystem before?","current_problem":{"goal":"fix failing architecture guardrail test","surface":"tests/config/test_architecture_boundaries.py and app layer imports","obstacle":"entrypoint handler appears to import startup wiring","hypothesis":"dependency shape should move out of startup"}}'
```

## Teach

Teach is for explicit user-provided knowledge, not normal task context or closeout.

```bash
shellbrain teach --json '{"text":"In this repo, startup wires dependencies but should not own workflow behavior.","current_problem":{"goal":"record architecture preference","surface":"startup and clean architecture","obstacle":"agents may put behavior in startup","hypothesis":"teach should become a durable preference or concept claim"}}'
```

Shellbrain stores the teaching as evidence and immediately runs a separate teach agent that may write memories or concept graph updates.

## Query Examples

Prior attempts:

```bash
shellbrain recall --json '{"query":"Have we seen this oauth callback loop in staging before?","current_problem":{"goal":"fix oauth callback loop","surface":"auth callback route and staging login flow","obstacle":"callback redirects repeatedly instead of completing login","hypothesis":"cookie state is not surviving the callback"}}'
```

Constraints and preferences:

```bash
shellbrain recall --json '{"query":"What repo constraints or user preferences matter for this auth refactor?","current_problem":{"goal":"refactor auth callback handling","surface":"auth routes and callback tests","obstacle":"unclear existing conventions for redirect behavior","hypothesis":"there is a repo-specific callback invariant"}}'
```

Area-specific facts and changes:

```bash
shellbrain recall --json '{"query":"What facts or recent changes matter around the payments retry worker?","current_problem":{"goal":"debug retry worker failure","surface":"payments retry worker","obstacle":"retry state diverges after timeout","hypothesis":"recent retry policy change affected idempotency"}}'
```

No hypothesis yet:

```bash
shellbrain recall --json '{"query":"Have we seen this kind of flaky test before?","current_problem":{"goal":"stabilize flaky test","surface":"checkout integration test","obstacle":"failure is intermittent and not yet explained","hypothesis":"none yet"}}'
```

## Query Quality

Good recall queries name the actual failure mode, subsystem, decision, file area, or constraint.

Avoid:

- `what should I know about this repo?`
- `what should I do?`
- `anything relevant?`

## Response Use

Treat the returned brief as advisory memory.

Use it to find:

- prior cases
- likely files or functions
- user preferences
- architectural constraints
- known traps
- concept orientation
- gaps where Shellbrain has no useful context

Current repo state remains ground truth.

## Worker Boundary

Working agents should normally call `shellbrain recall`. They may call `shellbrain teach` only for explicit user teaching.

Working agents should not call:

```bash
shellbrain read
shellbrain events
shellbrain memory add
shellbrain memory update
shellbrain concept add
shellbrain concept update
shellbrain scenario record
```

Those commands are internal-agent interfaces. Shellbrain recall and knowledge building use them under the hood.
