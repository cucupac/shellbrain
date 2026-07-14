# Shellbrain Recall Session Workflow

## Mental Model

Shellbrain is persistent memory for agent work. The working agent does not browse raw memories or write durable knowledge directly.

The working-agent interface is:

```bash
shellbrain recall "<targeted natural-language question>"
```

Recall asks Shellbrain's internal recall agent to inspect relevant memories, concepts, scenarios, and recent episode context, then return a compact brief for the current problem.

Treat current repo state as ground truth. Treat recall as advisory long-term memory that helps answer: "Have I seen anything like this before, and what was useful?"

## Bootstrap

Treat `shellbrain init` as first-time bootstrap plus repair, not as a routine start-of-session command.

Normal session rhythm:

- if Shellbrain already works in this repo, go straight to `recall`
- if readiness is unclear, run `shellbrain admin doctor`
- if Shellbrain has never been bootstrapped on this machine, this repo has never been registered, or `doctor` says `repair_needed`, run `shellbrain init`

Bootstrap and repair path:

```bash
shellbrain init
shellbrain admin doctor
```

In Codex Desktop and similar tool shells, if direct `shellbrain` calls fail in the current session, do a one-time login-shell retry:

```bash
zsh -lc 'source ~/.zprofile >/dev/null 2>&1; command -v shellbrain'
```

If the host shell is bash instead of zsh, use:

```bash
bash -lc 'source ~/.bash_profile >/dev/null 2>&1; command -v shellbrain'
```

Do not keep sourcing the login profile on every Shellbrain command. Once `shellbrain` is visible, use plain `shellbrain ...`.

If the one-time login-shell retry still cannot find `shellbrain`, inspect Python's user script directory:

```bash
python3 -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))"
```

If that directory contains `shellbrain`, call it directly or add that directory to the login profile PATH and retry. If it does not, reinstall the Shellbrain CLI.

## Repo Targeting

- Default to the current working directory when it is the repo you are working in.
- Use `--repo-root /absolute/path/to/repo` when your shell is elsewhere.
- Treat path as operational context, not durable identity.
- Shellbrain normally derives durable repo identity from normalized git remote.

## Attention Programming

Maintain this tuple while you work:

`goal | surface | obstacle | hypothesis`

Whenever that tuple changes materially, or you hit a boundary state, pause and say one `SB:` line out loud by actually generating it as output.

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

If prior context might help:

`SB: recall | <goal> | <surface> | <obstacle> | <hypothesis-or-trigger>`

Then call recall with one targeted natural-language query.

If recall would not add information:

`SB: skip | same signature | <one-line reason>`

Then continue. Do not call recall reflexively.

## Recall Query

Pass one self-contained question as a quoted positional argument. Recall receives only this query, so include relevant task context naturally.

Example:

```bash
shellbrain recall "What architectural constraints matter before moving this CLI handler?"
```

## Query Guidance

Good recall queries are concrete. Name the failure mode, subsystem, decision, file area, or constraint.

Prior attempt query:

```bash
shellbrain recall "I'm debugging a migration lock timeout. What prior context matters?"
```

Constraint query:

```bash
shellbrain recall "What repo constraints or user preferences matter for this auth callback refactor?"
```

Area-specific query:

```bash
shellbrain recall "What facts or recent changes matter around the payments retry worker timeout?"
```

Avoid generic prompts like:

- `what should I know about this repo?`
- `what should I do?`
- `anything relevant?`

## How To Use The Brief

Recall returns a compact brief. Use it to identify:

- relevant prior cases
- files or functions worth inspecting
- constraints and preferences
- known traps
- concept orientation
- gaps where Shellbrain found nothing useful

Use current repo state to verify anything operational before editing.

## Worker Boundary

As the working agent, use `shellbrain recall` for normal task context.

Use `shellbrain teach` only when the user explicitly asks you to store, remember, or teach Shellbrain a specific point:

```bash
shellbrain teach --json '{"text":"In this repo, startup wires dependencies but should not own workflow behavior.","current_problem":{"goal":"record architecture preference","surface":"startup and clean architecture","obstacle":"agents may put behavior in startup","hypothesis":"teach should become a durable preference or concept claim"}}'
```

Teach stores the user statement as evidence and immediately runs a separate teach agent. Do not use it as a generic closeout summary.

If you changed any files since your last user-facing response, run `shellbrain snapshot` exactly once after validation and immediately before your next user-facing response. Do this on every response cycle where files changed; skip only when no files changed:

```bash
shellbrain snapshot
```

Snapshot captures exact repo code state in repo-local shadow Git. The knowledge-builder agent later links valid snapshot ranges to solved problem runs.

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

Those are internal-agent commands. Shellbrain's internal recall agent handles raw retrieval and synthesis. Shellbrain's knowledge-builder agent consolidates durable memories, concepts, and scenarios after the session lifecycle.

## Recovery

- New agent session, but Shellbrain was already set up:
  do not rerun `init`. Use `recall`. Use `doctor` only if readiness is unclear.

- `shellbrain: command not found`:
  retry through `zsh -lc 'source ~/.zprofile >/dev/null 2>&1; command -v shellbrain'` first. Do not keep prefixing every Shellbrain command with profile sourcing.

- `shellbrain init` fails or `doctor` shows `repair_needed`:
  rerun `shellbrain init`. That is the normal repair path.

- Recall returns no relevant context:
  continue from current repo evidence. A truthful no-context brief is a valid result.
