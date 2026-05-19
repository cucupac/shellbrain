# Shellbrain Recall Session Workflow

## Mental Model

Shellbrain is persistent memory for agent work. The working agent does not browse raw memories or write durable knowledge directly.

The working-agent interface is:

```bash
shellbrain recall
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

Then call recall with a targeted query and `current_problem`.

If recall would not add information:

`SB: skip | same signature | <one-line reason>`

Then continue. Do not call recall reflexively.

## Recall Payload

`current_problem` is required. It has four required non-empty fields:

- `goal`: what you are trying to accomplish
- `surface`: the code, subsystem, behavior, or decision area
- `obstacle`: what is blocking or uncertain
- `hypothesis`: your current theory, or `"none yet"`

Example:

```bash
shellbrain recall --json '{"query":"What architectural constraints matter before moving this CLI handler?","current_problem":{"goal":"move CLI handler without breaking clean architecture","surface":"entrypoints, startup, and handler dependency wiring","obstacle":"handler currently imports startup types","hypothesis":"startup should construct dependencies but handler should receive protocols"}}'
```

## Query Guidance

Good recall queries are concrete. Name the failure mode, subsystem, decision, file area, or constraint.

Prior attempt query:

```bash
shellbrain recall --json '{"query":"Have we seen this migration lock timeout before?","current_problem":{"goal":"fix migration test failure","surface":"database migrations and schema setup","obstacle":"migration blocks waiting on lock","hypothesis":"a previous test leaves a transaction open"}}'
```

Constraint query:

```bash
shellbrain recall --json '{"query":"What repo constraints or user preferences matter for this auth refactor?","current_problem":{"goal":"refactor auth callback handling","surface":"auth routes and callback tests","obstacle":"unclear existing conventions for redirect behavior","hypothesis":"there is a repo-specific callback invariant"}}'
```

Area-specific query:

```bash
shellbrain recall --json '{"query":"What facts or recent changes matter around the payments retry worker?","current_problem":{"goal":"debug retry worker failure","surface":"payments retry worker","obstacle":"retry state diverges after timeout","hypothesis":"recent retry policy change affected idempotency"}}'
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

As the working agent, use `shellbrain recall` only.

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
