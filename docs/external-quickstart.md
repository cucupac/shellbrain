# Advanced Operator Guide

## Normal Product Path

The normal Shellbrain path should be:

```bash
curl -L shellbrain.ai/install | bash
```

The installer already runs `shellbrain init` for you.

The normal upgrade path should be:

```bash
shellbrain upgrade
```

or:

```bash
curl -L shellbrain.ai/upgrade | bash
```

That bootstrap step is machine-level. It prepares the managed runtime, installs host integrations, and leaves repo registration to first use inside a repo.

Managed-local requirements:

- macOS or Linux
- Python 3.11+ required
- Docker installed and the daemon running
- first init downloads a local embedding model
- PostgreSQL + pgvector run inside the managed Docker runtime
- Windows is not supported in this path
- external Postgres remains advanced/operator-managed

Manual install path:

```bash
pipx install shellbrain
shellbrain init
shellbrain admin doctor
```

Manual/advanced upgrade path:

```bash
pipx upgrade shellbrain && shellbrain init
```

If that works, stop here. The rest of this document is for advanced operators, legacy environments, or manual recovery.

## When This Guide Matters

Use this guide when:

- `shellbrain admin doctor` says the managed runtime is blocked
- you are maintaining an older env-var/DSN based install
- you are doing packaging, editable-install, or recovery work
- you are preparing for future external-Postgres adoption

## Transition Guidance

Shellbrain now uses one machine-local managed instance reused across repos.

That means:

- normal users should not need raw DSNs
- normal users should not run Docker commands manually
- normal users should not run `shellbrain admin migrate` manually
- normal users should not hand-edit machine config
- normal users should not need to know where models, backups, or the managed Postgres data dir live

Machine-owned state lives under `$SHELLBRAIN_HOME`, which defaults to `~/.shellbrain`. That root contains machine config, the managed Postgres bind mount, model cache, and backups.

## Legacy / Manual Bootstrap

If you are on a pre-productized build, the older operator path is:

```bash
export SHELLBRAIN_DB_DSN='postgresql+psycopg://<app-user>:<app-password>@localhost:5432/<database-name>'
export SHELLBRAIN_DB_ADMIN_DSN='postgresql+psycopg://<admin-user>:<admin-password>@localhost:5432/<database-name>'
shellbrain admin migrate
shellbrain admin doctor
```

In Codex Desktop and similar tool shells, do a one-time login-shell retry first if direct `shellbrain` calls fail:

```bash
zsh -lc 'source ~/.zprofile >/dev/null 2>&1; command -v shellbrain'
```

If the host shell is bash instead of zsh, use:

```bash
bash -lc 'source ~/.bash_profile >/dev/null 2>&1; command -v shellbrain'
```

Fish PATH setup is written to `~/.config/fish/conf.d/shellbrain.fish`; open a new fish session and run `shellbrain --help`.

Do not keep sourcing the login profile on every Shellbrain command. Sourcing is only necessary when a fresh tool shell does not yet have the login PATH needed to find the CLI. Once `shellbrain` is visible, use plain `shellbrain ...`. If the host tool keeps starting fresh shells without your login PATH, reuse the absolute path returned by `command -v shellbrain` instead of re-sourcing the profile on every call.

If the one-time login-shell retry still cannot find `shellbrain`, inspect Python's user script directory:

```bash
python3 -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))"
```

If that directory contains `shellbrain`, call it directly or add that directory to the login profile PATH and retry. If it does not, reinstall the Shellbrain CLI.

The repo Dockerfile is for packaging and development smoke coverage. It is not the end-user runtime path.

Steady-state working-agent usage, once the CLI is visible, should look like:

```bash
shellbrain recall --json '{"query":"Have we seen this migration lock timeout before?","current_problem":{"goal":"fix migration test failure","surface":"database migrations and schema setup","obstacle":"migration blocks waiting on lock","hypothesis":"a previous test leaves a transaction open"}}'
```

## Repo Targeting

- Use the current working directory when already inside the repo.
- Use `--repo-root /absolute/path/to/repo` when your shell is elsewhere.
- Treat repo path as operational context.
- Shellbrain should normally infer durable repo identity from normalized git remote.
- It prefers `origin`, then a single remaining remote.
- If multiple remotes exist and none is `origin`, rerun with `--repo-id`.
- If no usable remote exists, Shellbrain falls back to a weak-local identity tied to the current path.

## Query and Session Usage

Even in advanced/operator environments, the working-agent usage model stays simple: use recall when prior context may help.

As the working agent, use Shellbrain through `shellbrain recall`.

1. Maintain a mental summary of the current subproblem as `goal | surface | obstacle | hypothesis`.
2. Whenever that tuple changes materially, or you hit a boundary state, pause and say one `SB:` line out loud by actually generating it as output.
3. Use `SB: recall | <goal> | <surface> | <obstacle> | <hypothesis-or-trigger>` if prior memory might help.
4. Call `shellbrain recall` with a concrete query and required `current_problem`.
5. Use `SB: skip | same signature | <one-line reason>` when the tuple has not meaningfully changed and there is no new evidence, failure, or uncertainty.
6. Do not call recall reflexively.

Example:

```bash
shellbrain recall --json '{"query":"What repo constraints or user preferences matter for this auth refactor?","current_problem":{"goal":"refactor auth callback handling","surface":"auth routes and callback tests","obstacle":"unclear existing conventions for redirect behavior","hypothesis":"there is a repo-specific callback invariant"}}'
```

Avoid vague queries like "what should I know about this repo?", "what should I do?", or "anything relevant?"

Working agents should not call `shellbrain read`, `shellbrain events`, `shellbrain memory`, `shellbrain concept`, or `shellbrain scenario`. Those are internal-agent commands. Shellbrain's internal recall and knowledge-builder agents handle raw retrieval, synthesis, durable memory writing, concept updates, and scenario recording.

## Host Integration

- `shellbrain init` installs a managed Shellbrain block in `${CODEX_HOME:-~/.codex}/AGENTS.md`.
- `shellbrain init` installs the personal Codex skill in `${CODEX_HOME:-~/.codex}/skills`.
- `shellbrain init` installs a managed Shellbrain block in `~/.claude/CLAUDE.md`.
- `shellbrain init` installs the personal Claude skill in `~/.claude/skills`.
- `shellbrain init` installs the personal Cursor skill in `${CURSOR_HOME:-~/.cursor}/skills`.
- `shellbrain init` installs the Claude global SessionStart hook in `~/.claude/settings.json`.
- Shellbrain creates `~/.claude/settings.json` if needed and merges one managed hook entry without overwriting unrelated settings.
- Repo-local Claude hook install is now an explicit override/repair path, not the default integration.
- Cursor foreground chat support is passive and untrusted in v1; Shellbrain reads the active Composer thread from Cursor's local SQLite state.
- Cursor background agents, rules, custom modes, and extension bridges are not part of this path yet.
- Manual host asset repair path:

```bash
shellbrain admin install-host-assets --host auto
shellbrain admin install-claude-hook --repo-root /path/to/repo
```

## Repo Registration

- Repo registration is no longer part of the initial machine bootstrap requirement.
- On first real `recall` inside a git repo, Shellbrain auto-registers that repo at the git root.
- If you run Shellbrain outside a git repo, it does not auto-register arbitrary directories like `~`.
- Use `--repo-root` and `--repo-id` when you need to target or override repo identity explicitly.

## Backups and Recovery

Shellbrain exposes first-class logical backups:

```bash
shellbrain admin backup create
shellbrain admin backup list
shellbrain admin backup verify
shellbrain admin backup restore --target-db shellbrain_restore_001
shellbrain admin doctor
```

Backups default to `$SHELLBRAIN_HOME/backups`, which is `~/.shellbrain/backups` unless `SHELLBRAIN_HOME` is set. The Docker bind-mounted Postgres data dir protects against container loss, but it is not a backup by itself.

DB-backed tests are a separate workflow. For managed local Shellbrain, keep the live managed database for memories only and use the dedicated repo-owned test host from `docker-compose.test.yml` via `scripts/run_tests` for destructive test setup and scratch validation.

If repair is needed:

1. run `shellbrain admin doctor`
2. prefer rerunning `shellbrain init`
3. only drop to manual DSN or Docker repair if the managed runtime is clearly blocked

## Local Migration Helper

If your local Docker-backed Postgres is still the older `memory-postgres` setup, run:

```bash
bash scripts/migrate_local_postgres_to_shellbrain
```

That helper is idempotent. It:

- creates `shellbrain_admin` and `shellbrain_app`
- clones the old `memory` database into `shellbrain`
- restarts the Docker container as `shellbrain-postgres`
- keeps the legacy `memory` database in place as a fallback until you remove it

## External Postgres

External Postgres is an advanced/operator path and is intentionally not the Phase 1 happy path.

The future direction is:

- explicit adoption through `shellbrain init --mode external --admin-dsn ... --app-dsn ...`
- no hand-authored config files
- fail-closed refusal for non-empty unstamped databases

Until that lands, treat external-DB setups as operator-managed.
