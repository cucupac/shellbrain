---
name: shellbrain-session-start
description: Use when Cursor should get up to speed in any repo with the installed shellbrain CLI, retrieve prior repo context, inspect recent transcript evidence, and write back durable Shellbrain entries.
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
4. If `doctor` reports repair is needed, rerun `shellbrain init`.
5. If direct `shellbrain` calls fail in the current Cursor shell, retry through a login shell that sources the user's login profile:
   - `zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'`
   - `bash -lc 'source ~/.bash_profile >/dev/null 2>&1; shellbrain --help'`
6. If the wrapped login-shell check still cannot find `shellbrain`, inspect Python's user script directory:
   - `python3 -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))"`
7. Resolve the target repo:
   - use the current working directory when already inside the repo
   - pass `--repo-root /absolute/path/to/repo` when working from somewhere else
8. Start with focused `read` queries about the concrete problem, subsystem, decision, or constraint you are working on. Do not start with vague prompts like "what should I know about this repo?"
9. Before `create` or any evidence-bearing `update`, run `shellbrain events --json '{"limit":10}'`.
10. Reuse returned `data.events[].id` values verbatim as `evidence_refs`.
11. At session end, normalize the episode into durable memories and record `utility_vote` updates for memories that helped or misled.

## Operating Rules

- Never invent `evidence_refs`.
- Skip the write if `events` returns nothing useful or the evidence is ambiguous.
- Prefer `scope: "repo"` unless the knowledge is intentionally cross-repo.
- Store durable, reusable knowledge. Do not store transient chatter, raw logs, or short-lived status.
- Use `read` again before writing when you need to check whether a memory already exists or whether an `update` is more appropriate than a new `create`.

If you need deeper guidance, read https://shellbrain.ai/agents.
