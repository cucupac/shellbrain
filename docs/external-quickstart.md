# External Quickstart

## Goal

Use Shellbrain from a normal agent session in a different repo.

## Install

Local editable install:

```bash
pip install -e /absolute/path/to/shellbrain
```

Git install:

```bash
pip install git+file:///absolute/path/to/shellbrain
```

## Bootstrap

```bash
export SHELLBRAIN_DB_DSN='postgresql+psycopg://shellbrain:shellbrain@localhost:5432/shellbrain'
shellbrain admin migrate
```

## Canonical Workflow

1. Use `read` for prior context:

```bash
shellbrain read --json '{"query":"what should I remember about the deploy failure?"}'
```

2. Use `events` before every write:

```bash
shellbrain events --json '{"limit":10}'
```

3. Use returned `episode_event` ids verbatim in `create` or any evidence-bearing `update`:

```bash
shellbrain create --json '{"memory":{"text":"Deploy failed because APP_ENV was unset","kind":"problem","evidence_refs":["evt-123"]}}'
shellbrain update --json '{"memory_id":"mem-123","update":{"type":"association_link","to_memory_id":"mem-456","relation_type":"associated_with","evidence_refs":["evt-456"]}}'
```

## Rules

- Never invent `evidence_refs`.
- Skip the write if evidence is missing or ambiguous.
- Prefer `create` for durable facts, problems, preferences, decisions, and reusable operating knowledge.
- Prefer `update` for archive state changes, fact evolution, and association/link maintenance.
- `archive_state` does not use `evidence_refs`; the evidence-bearing update types carry them inside the `update` object.

## Repo Targeting

- `--repo-root` targets a repo even when your shell is elsewhere.
- `--repo-id` overrides the default `basename(repo_root)` inference.
- `--no-sync` suppresses the repo-local background transcript poller and `.shellbrain` runtime files.

Examples:

```bash
shellbrain --repo-root /path/to/other-repo read --json '{"query":"what repo conventions matter here?"}'
shellbrain --repo-root /path/to/other-repo --no-sync events --json '{}'
```

## Codex Skill

This repo ships a versioned session-start skill at [`skills/shellbrain-session-start/SKILL.md`](../skills/shellbrain-session-start/SKILL.md).

To use it in Codex, copy or symlink the directory into `$CODEX_HOME/skills`:

```bash
mkdir -p "$CODEX_HOME/skills"
ln -s /absolute/path/to/shellbrain/skills/shellbrain-session-start "$CODEX_HOME/skills/shellbrain-session-start"
```
