---
name: shellbrain-session-start
description: Use when Cursor should get up to speed in any repo with the installed shellbrain CLI, or when work shifts to a new surface, repeated failure suggests prior memory may help, a hypothesis changes, an evidence-bearing write is about to happen, or closeout should record durable learnings.
---

# Shellbrain Session Start

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

`shellbrain init` is first-time bootstrap and repair. It is not a per-session ritual.

## Quick Start

1. If Shellbrain has never been bootstrapped on this machine, the current repo has never been registered, or the user says Shellbrain setup is broken, run `shellbrain init`.
2. Otherwise, do not rerun `init` just because a new agent session started. Start with focused `read` queries right away.
3. If readiness is unclear, inspect with `shellbrain admin doctor` instead of rerunning `init` by reflex.
4. If `doctor` reports `repair_needed`, rerun `shellbrain init`.
5. If direct `shellbrain` calls fail in the current Cursor shell, retry through a login shell that sources the user's login profile:
   - `zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'`
   - `bash -lc 'source ~/.bash_profile >/dev/null 2>&1; shellbrain --help'`
6. If the wrapped login-shell check still cannot find `shellbrain`, inspect Python's user script directory:
   - `python3 -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))"`
7. Resolve the target repo:
   - use the current working directory when already inside the repo
   - pass `--repo-root /absolute/path/to/repo` when working from somewhere else
8. Start with focused `read` queries about the concrete problem, subsystem, decision, or constraint you are working on. Do not start with vague prompts like "what should I know about this repo?"

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

## Write Discipline

Run `shellbrain events` before any evidence-bearing `create` or `update`. This is mandatory.

- `shellbrain events --json '{"limit":10}'`
- reuse returned `data.events[].id` values verbatim as `evidence_refs`
- never invent `evidence_refs`
- skip the write if `events` returns nothing useful or the evidence is ambiguous

## Closeout

When work is solved, write durable memories and run `utility_vote` updates.

At session end, normalize the episode into durable memories:

- store the `problem`
- store each `failed_tactic`
- store the `solution`
- store any durable `fact`, `preference`, or `change`
- record `utility_vote` updates for memories that helped or misled

If you need deeper guidance, read https://shellbrain.ai/agents.
