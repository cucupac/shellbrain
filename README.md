# Building a Brain

`shellbrain` is a repo-scoped long-term context system for agent sessions.

Think of it as a case-based memory system with two layers:

- durable memories:
  - `problem`
  - `solution`
  - `failed_tactic`
  - `fact`
  - `preference`
  - `change`
- episodic evidence:
  - transcript-derived `episode_event` records that ground writes

It exposes four agent-facing operations:

- `read` recalls durable memories related to the current problem or subproblem
- `events` inspects recent episodic evidence
- `create` adds new durable Shellbrain entries with explicit `evidence_refs`
- `update` records utility, links, and lifecycle changes on existing entries

## Install Once Per Machine

Treat `shellbrain` as a machine-level CLI, not a per-repo dependency. The normal model is a one-time global install.

Preferred global install with `pipx`:

```bash
pipx install --editable /absolute/path/to/shellbrain
```

Fallback user-level editable install:

```bash
python3 -m pip install --user --break-system-packages --editable /absolute/path/to/shellbrain
```

If you use the user-level install, ensure your user Python bin is on `PATH`:

```bash
export PATH="$(python3 -m site --user-base)/bin:$PATH"
```

## Bootstrap

Export `SHELLBRAIN_DB_DSN` from your shell profile, then apply packaged migrations once:

```bash
export SHELLBRAIN_DB_DSN='postgresql+psycopg://shellbrain:shellbrain@localhost:5432/shellbrain'
shellbrain admin migrate
```

## Migrate Existing Local Postgres

If your local Docker-backed Postgres is still the older `memory-postgres` setup, run:

```bash
bash scripts/migrate_local_postgres_to_shellbrain
```

This migration is idempotent. It:

- creates the `shellbrain` role inside the existing cluster
- clones the old `memory` database into a new `shellbrain` database
- restarts the Docker container as `shellbrain-postgres`
- keeps the legacy `memory` database in place as a fallback until you choose to remove it

## Typical Workflow

1. Start with focused retrieval queries about the concrete problem, subsystem, constraint, or decision you are working on. Do not start with vague prompts like "what should I know about this repo?"
2. Use `read` again during the task whenever the search shifts or a memory might become useful midway through the work.
3. Before every evidence-bearing write, run `shellbrain events --json '{}'` so you can inspect concrete `episode_event` ids.
4. At session end, normalize what happened into durable memories:
   - the `problem`
   - each `failed_tactic`
   - the `solution`
   - any durable `fact`, `preference`, or `change`
   - `utility_vote` updates for memories that helped or misled, using a `-1.0` to `1.0` scale where negative votes mean unhelpful and positive votes mean helpful

Never invent `evidence_refs`. If `events` returns nothing useful or the evidence is ambiguous, skip the write and try again later.

Use `--repo-root` when your current working directory is not the repo you want to target. Use `--repo-id` only when you need to override the default `basename(repo_root)` inference.

## More

- Quickstart: [`docs/external-quickstart.md`](docs/external-quickstart.md)
- Session-start skill: [`skills/shellbrain-session-start/SKILL.md`](skills/shellbrain-session-start/SKILL.md)
