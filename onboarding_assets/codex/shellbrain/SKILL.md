---
name: shellbrain
description: Use when an agent should remember to ask Shellbrain for targeted recall at task start, subproblem changes, repeated failures, hypothesis changes, or closeout.
---

# Shellbrain Recall Workflow

## Purpose

Shellbrain is a persistent memory system for agent work.

As the working agent, your interface is:

```bash
shellbrain recall
```

Recall returns a compact brief synthesized from prior memories, concepts, scenarios, and recent episode context. It is meant to reduce wasted exploration and help you decide where to look next.

Do not call Shellbrain internal commands directly. `read`, `events`, `memory`, `concept`, and `scenario` are for Shellbrain's internal agents.

## Quick Start

Do not run `shellbrain init` at the start of every session.

Use this order:

1. If Shellbrain is missing or broken, run `shellbrain admin doctor`.
2. If doctor says repair is needed, run `shellbrain init`.
3. Otherwise, use `shellbrain recall` with a targeted query and `current_problem`.

If `shellbrain` is not found, do a one-time PATH check:

```bash
zsh -lc 'source ~/.zprofile >/dev/null 2>&1; command -v shellbrain'
```

If the host shell is bash instead of zsh, use:

```bash
bash -lc 'source ~/.bash_profile >/dev/null 2>&1; command -v shellbrain'
```

Once found, use plain `shellbrain ...`. Do not keep sourcing the login profile on every Shellbrain command.

If the one-time login-shell retry still cannot find `shellbrain`, inspect Python's user script directory:

```bash
python3 -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))"
```

If that directory contains `shellbrain`, call it directly or add that directory to the login profile PATH and retry. If it does not, reinstall the Shellbrain CLI.

## Repo Targeting

- Use the current working directory when already inside the repo.
- Pass `--repo-root /absolute/path/to/repo` when your shell is elsewhere.
- Treat repo path as operational context. Shellbrain normally derives durable repo identity from normalized git remote.

## Attention Programming

Maintain this tuple while you work:

`goal | surface | obstacle | hypothesis`

Pause and emit an `SB:` line when the tuple changes or a boundary state occurs.

Boundary states:

- The goal changed.
- The surface changed.
- The obstacle changed.
- The hypothesis changed.
- The same approach failed twice.
- An error is repeating.
- You are switching subsystems or files.
- You are about to make an important implementation decision.
- You are closing out a task.

If recall might help:

`SB: recall | <goal> | <surface> | <obstacle> | <hypothesis-or-trigger>`

Then call recall.

If recall would not add information:

`SB: skip | same signature | <one-line reason>`

Then continue.

## Recall Payload

`current_problem` is required. All four fields must be non-empty strings.

If you do not have a hypothesis yet, use `"none yet"`.

```bash
shellbrain recall --json '{"query":"Have we seen this failure mode or subsystem before?","current_problem":{"goal":"fix failing architecture guardrail test","surface":"tests/config/test_architecture_boundaries.py and app layer imports","obstacle":"entrypoint handler appears to import startup wiring","hypothesis":"dependency shape should move out of startup"}}'
```

## Query Guidance

Good recall queries are concrete. Name the failure mode, subsystem, decision, file area, or constraint.

Good examples:

```bash
shellbrain recall --json '{"query":"Have we seen this migration lock timeout before?","current_problem":{"goal":"fix migration test failure","surface":"database migrations and schema setup","obstacle":"migration blocks waiting on lock","hypothesis":"a previous test leaves a transaction open"}}'
```

```bash
shellbrain recall --json '{"query":"What architectural constraints matter before moving this CLI handler?","current_problem":{"goal":"move CLI handler without breaking clean architecture","surface":"entrypoints, startup, and handler dependency wiring","obstacle":"handler currently imports startup types","hypothesis":"startup should construct dependencies but handler should receive protocols"}}'
```

```bash
shellbrain recall --json '{"query":"What user preferences matter for this refactor?","current_problem":{"goal":"clean up Shellbrain onboarding assets","surface":"AGENTS.md and shellbrain skill","obstacle":"old guidance teaches internal commands to workers","hypothesis":"worker guidance should only teach recall"}}'
```

Avoid vague queries:

- `what should I know about this repo?`
- `what should I do?`
- `anything relevant?`

## How To Use The Brief

Treat recall as advisory memory, not ground truth.

Use the brief to identify:

- relevant prior cases
- files or functions worth inspecting
- constraints and preferences
- known traps
- concept orientation
- gaps where Shellbrain found nothing useful

Current repo state remains the source of truth.

## What Not To Do

Do not call:

```bash
shellbrain read
shellbrain events
shellbrain memory add
shellbrain memory update
shellbrain concept add
shellbrain concept update
shellbrain scenario record
```

Those are internal-agent commands.

Do not manually write memories at closeout. Shellbrain's knowledge-builder agent consolidates episodes after the session lifecycle.

## Resources

- Read [references/session-workflow.md](references/session-workflow.md) for the detailed recall cadence and attention habit.
- Read [references/request-shapes.md](references/request-shapes.md) for the required `shellbrain recall` payload shape.
