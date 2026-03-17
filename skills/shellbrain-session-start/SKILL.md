---
name: shellbrain-session-start
description: Use when Codex should get up to speed in any repo with the installed shellbrain CLI, retrieve prior repo context, inspect recent transcript evidence, and write back durable Shellbrain entries. Trigger when the user asks to use shellbrain, wants prior repo recall, wants to preserve durable learnings, or starts a session that should reuse long-term repo context.
---

# Shellbrain Session Start

## Overview

Get up to speed in the target repo with Shellbrain before doing substantial work, then write back only durable knowledge that is grounded in stored transcript evidence.

## Quick Start

1. Check that Shellbrain is available with `shellbrain --help`.
2. If the CLI is missing, ask the operator to install Shellbrain, set `SHELLBRAIN_DB_DSN`, and run `shellbrain admin migrate`.
3. Resolve the target repo:
   - Use the current working directory when already inside the repo.
   - Pass `--repo-root /absolute/path/to/repo` when working from somewhere else.
   - Pass `--repo-id` only when `basename(repo_root)` is not the right repo identifier.
4. Start with `shellbrain read --json '{"query":"what should I know about this repo or task before I start?"}'`.
5. Before `create` or any evidence-bearing `update`, run `shellbrain events --json '{"limit":10}'`.
6. Reuse returned `data.events[].id` values verbatim as `evidence_refs`.
7. Use the exact payload shapes in [references/request-shapes.md](references/request-shapes.md).

## Operating Rules

- Never invent `evidence_refs`.
- Skip the write if `events` returns nothing useful or the evidence is ambiguous.
- Prefer `scope: "repo"` unless the knowledge is intentionally cross-repo.
- Store durable, reusable knowledge. Do not store transient chatter, raw logs, or short-lived status.
- Treat `--no-sync` narrowly: it suppresses the background poller and `.shellbrain` runtime artifacts after a successful command, but `shellbrain events` still performs an inline sync to fetch the newest repo-matching transcript evidence.
- Use `read` again before writing when you need to check whether a memory already exists or whether an update is more appropriate than a new create.

## Write Heuristics

- Use `create` for new durable facts, problems, failed tactics, preferences, solutions, and change records.
- Use `update` for archive state changes, utility votes, fact evolution links, and association links.
- Use `archive_state` when the entry should simply be archived or unarchived.
- Use the evidence-bearing update types when the update itself depends on a concrete transcript event.

## Resources

- Read [references/session-workflow.md](references/session-workflow.md) for repo targeting, host assumptions, recovery steps, and storage heuristics.
- Read [references/request-shapes.md](references/request-shapes.md) for valid JSON payloads and minimal command examples.
