# Building a Brain

`shellbrain` is a repo-scoped long-term context system for agent sessions.

It exposes four agent-facing operations:
- `read` for retrieval-only recall
- `events` for inspecting recent host transcript evidence
- `create` for adding new Shellbrain entries with explicit `evidence_refs`
- `update` for evidence-backed changes to existing entries

## Install

Editable install from a local checkout:

```bash
pip install -e .
```

Install from a git URL:

```bash
pip install git+file:///absolute/path/to/shellbrain
```

## Bootstrap

Set `SHELLBRAIN_DB_DSN`, then apply packaged migrations:

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

1. `shellbrain read --json '{"query":"..."}'` when you need prior repo context.
2. `shellbrain events --json '{}'` before every write so you can inspect concrete `episode_event` ids.
3. `shellbrain create ...` or an evidence-bearing `shellbrain update ...` with those exact ids as `evidence_refs`.

Never invent `evidence_refs`. If `events` returns nothing useful or the evidence is ambiguous, skip the write and try again later.

Use `--repo-root` when your current working directory is not the repo you want to target. Use `--repo-id` only when you need to override the default `basename(repo_root)` inference. Successful operational commands start the repo-local sync poller by default; add `--no-sync` to suppress that side effect.

## More

- Quickstart: [`docs/external-quickstart.md`](docs/external-quickstart.md)
- Session-start skill: [`skills/shellbrain-session-start/SKILL.md`](skills/shellbrain-session-start/SKILL.md)
- Design and validation trail: [`insights/README.md`](insights/README.md)
