# Shellbrain quickstart

Install on macOS or Linux with Python 3.11 or newer:

```bash
curl -L shellbrain.ai/install | bash
```

The installer asks for storage selection, prepares the database and embedding model, and installs host integrations. Managed local storage requires Docker. Repositories register on first use. Existing external PostgreSQL storage remains supported through installer setup.

## Everyday commands

```bash
shellbrain recall "What prior context matters for this migration timeout?"
shellbrain snapshot
shellbrain upgrade
shellbrain --help
shellbrain --version
```

Use snapshot after code changes. Upgrade also repairs runtime setup and applies migrations. There is no separate public setup or migration command.

## Synthesis provider

Codex is the default. The selection persists across repositories:

```bash
shellbrain admin recall provider inception
shellbrain admin recall provider codex
shellbrain admin recall provider claude
```

For faster recall, [get an Inception API key](https://platform.inceptionlabs.ai/dashboard/api-keys), add `INCEPTION_API_KEY=your-key` to `~/.shellbrain/.env`, and run `shellbrain admin recall provider inception` once. Shellbrain loads the key automatically.

## Backups

```bash
shellbrain admin backup create
shellbrain admin backup list
shellbrain admin backup verify
shellbrain admin backup restore --target-db shellbrain_restore_scratch
```

Restore uses a scratch database. It does not overwrite the live database.

## Agent workflow

Ask a self-contained question about remembered project purpose, decisions, or past problems when that knowledge may help. Recall receives only this query. Use code search to check current behavior and paths. An incomplete answer does not prove a feature is absent. Snapshot repository changes after validation. Automatic knowledge building records useful lessons from session evidence. The internal `read`, `events`, `concept`, `memory`, and `scenario` endpoints serve those background agents.

## Repair

Start Docker if using managed storage. Run `shellbrain upgrade` to repair setup. If the executable is missing, rerun the installer. Follow the failing command's error message; users do not need a separate diagnostics command.
