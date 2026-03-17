# Shellbrain Session Workflow

## Bootstrap

Use Shellbrain only after confirming:

- `shellbrain --help` works.
- `SHELLBRAIN_DB_DSN` is set.
- `shellbrain admin migrate` has been run against the target database.

If the CLI is unavailable, stop and ask the operator to install Shellbrain first. Do not guess at a local checkout path from an unrelated repo.

## Repo Targeting

- Default to the current working directory when it is the repo you are working in.
- Use `--repo-root /absolute/path/to/repo` when your shell is elsewhere.
- Use `--repo-id` only when the target repo should not be identified by `basename(repo_root)`.
- The CLI accepts `--repo-root`, `--repo-id`, and `--no-sync` either before or after the subcommand.

## Canonical Start-of-Session Flow

1. Read first:

```bash
shellbrain read --json '{"query":"what should I know about this repo or task before I start?"}'
```

2. Narrow follow-up reads as needed:

```bash
shellbrain read --json '{"query":"what prior deploy failures or constraints matter here?","kinds":["problem","fact","change"]}'
```

3. Before any create or evidence-bearing update, inspect fresh evidence:

```bash
shellbrain events --json '{"limit":10}'
```

4. Reuse returned `data.events[].id` values verbatim as `evidence_refs`.

## What To Store

Prefer Shellbrain for durable knowledge that will matter in later sessions:

- recurring repo constraints
- decisions and why they were made
- deployment or runtime problems
- facts that future work depends on
- failed tactics worth not repeating
- stable preferences or operating conventions

Avoid writing:

- raw transcript excerpts
- temporary status updates
- one-off plans that were immediately discarded
- ambiguous claims that are not grounded in visible evidence

## Create vs Update

- Use `create` when the durable record does not exist yet.
- Use `update` when changing archive state or adding a relationship to an existing record.
- Run another `read` if you are not sure whether the memory already exists.

## Host and Evidence Assumptions

- `events` selects the newest repo-matching active session across the supported hosts.
- Supported hosts are Codex and Claude Code.
- Repo matching depends on transcript metadata whose working directory matches the target `repo_root`.
- `events` always performs an inline sync before returning recent stored events.

## Recovery

- `shellbrain: command not found`
  Ask the operator to install Shellbrain in the current environment.

- `SHELLBRAIN_DB_DSN is not set`
  Ask the operator to export the DB DSN, then rerun `shellbrain admin migrate` if the database is fresh.

- No active host session found
  Verify that the user is working in Codex or Claude Code, that transcript files exist, and that `repo_root` matches the repo used in that session.

- Evidence ref rejected or event not visible
  Rerun `shellbrain events` and use the returned ids verbatim. Do not reuse stale ids from memory.

- `--no-sync`
  Remember that it only suppresses the background poller. It does not prevent `events` from doing its foreground sync.
