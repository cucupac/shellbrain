# Shellbrain Session Start

## Overview

Use Shellbrain as a case-based reasoning system for long-running agent work.

Shellbrain has two layers:

- durable memories:
  - `problem`
  - `solution`
  - `failed_tactic`
  - `fact`
  - `preference`
  - `change`
- episodic evidence:
  - transcript-derived `episode_events` that justify writes

Treat current repo state as ground truth. Treat Shellbrain as advisory long-term memory that helps answer: "Have I seen anything like this before, and what was useful?"

## Quick Start

`shellbrain init` is first-time bootstrap and repair. It is not a per-session ritual.

1. If Shellbrain has never been bootstrapped on this machine, the current repo has never been registered, or the user says Shellbrain setup is broken, run `shellbrain init`.
2. Otherwise, do not rerun `init` just because a new agent session started. Start with focused `read` queries right away.
3. If readiness is unclear, inspect with `shellbrain admin doctor` instead of rerunning `init` by reflex.
4. If `doctor` reports `repair_needed`, rerun `shellbrain init` instead of trying to repair Shellbrain manually.
5. In Claude Code, if direct `shellbrain` calls fail in the current session, retry through a login shell that sources the user's login profile:
   - `zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'`
   - `bash -lc 'source ~/.bash_profile >/dev/null 2>&1; shellbrain --help'`
6. If the wrapped login-shell check still cannot find `shellbrain`, inspect Python's user script directory:
   - `python3 -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))"`
   If `shellbrain` exists there, call it directly or add that directory to the login profile PATH and retry. If it does not, reinstall the Shellbrain CLI.
7. Resolve the target repo:
   - use the current working directory when already inside the repo
   - pass `--repo-root /absolute/path/to/repo` when working from somewhere else
   - treat repo path as operational context; Shellbrain should normally derive durable repo identity from normalized git remote
8. Start with focused `read` queries about the concrete problem, subsystem, decision, or constraint you are working on. Do not start with vague prompts like "what should I know about this repo?"
9. Use a startup read bundle when appropriate:
   - prior attempts:
     `shellbrain read --json '{"query":"Have we seen this failure mode before?","kinds":["problem","solution","failed_tactic"]}'`
   - constraints and preferences:
     `shellbrain read --json '{"query":"What repo constraints or user preferences matter for this task?","kinds":["fact","preference","change"]}'`
   - area-specific facts:
     `shellbrain read --json '{"query":"What facts or changes matter in this subsystem?","kinds":["fact","change","problem","solution"]}'`

## Attention Programming

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

## Query Construction

When the answer is `SB: read`, build the query from the live tuple. Name the actual failure mode, subsystem, decision, or constraint.

Good query shapes:

- prior attempts for the current obstacle:
  `shellbrain read --json '{"query":"Have we seen this oauth callback loop in staging before?","kinds":["problem","solution","failed_tactic"]}'`
- constraints and preferences for the current surface:
  `shellbrain read --json '{"query":"What repo constraints or user preferences matter for this auth refactor?","kinds":["fact","preference","change"]}'`
- facts and changes for the subsystem you just entered:
  `shellbrain read --json '{"query":"What facts or recent changes matter around the payments retry worker?","kinds":["fact","change","problem","solution"]}'`

Avoid generic prompts like:

- "what should I know about this repo?"
- "what should I know before I start?"

Those are too vague for the actual retrieval model.

## Write Discipline

Run `shellbrain events` before any evidence-bearing `create` or `update`. This is mandatory.

```bash
shellbrain events --json '{"limit":10}'
```

Then reuse returned `data.events[].id` values verbatim as `evidence_refs`.

Hard rules:

- never invent `evidence_refs`
- skip the write if `events` returns nothing useful or the evidence is ambiguous
- use `read` again before writing if you need to check whether the memory already exists or whether an `update` is more appropriate than a new `create`

Durable memory kinds:

- `problem`
- `solution`
- `failed_tactic`
- `fact`
- `preference`
- `change`

Invariant:

- `solution` and `failed_tactic` require `links.problem_id`
- `problem`, `fact`, `preference`, and `change` do not accept `links.problem_id`

## Closeout

When work is solved, write durable memories and run `utility_vote` updates. Normalize the episode into durable memory:

1. store the `problem`
2. store each `failed_tactic`
3. store the `solution`
4. store any durable `fact`, `preference`, or `change`
5. record `utility_vote` updates for memories that helped or misled

Use `scope: "repo"` by default. Use `scope: "global"` only for intentionally cross-repo knowledge such as user-wide preferences or cross-project facts.

## Trusted Session Note

- `events` now syncs the exact trusted caller thread instead of mixing same-repo agent threads
- Claude trusted identity normally comes from the global Shellbrain SessionStart hook in `~/.claude/settings.json`; repo-local `.claude/settings.local.json` is the explicit override or repair path
- successful responses may include `data.guidance`; treat that as an internal Shellbrain nudge about pending utility votes or workflow reminders

## Resources

- Read https://shellbrain.ai/agents if you need the deeper system docs.
- Use the same payload shapes as the Codex skill docs when issuing `read`, `events`, `create`, or `update`.
