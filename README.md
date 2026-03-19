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

Treat `shellbrain` as a machine-level CLI, not a per-repo dependency. The normal product path is a one-time global install, then `shellbrain init` from any repo you want to register.

Preferred install with `pipx`:

```bash
pipx install shellbrain
```

Secondary install path:

```bash
python3 -m pip install shellbrain
```

Editable installs remain a development/operator path and are intentionally omitted from the normal user-facing flow.

## Bootstrap

From the repo you are working in:

```bash
shellbrain init
shellbrain admin doctor
```

`shellbrain init` is the normal bootstrap and repair path. In the managed-local happy path it owns Docker, Postgres provisioning, migrations, grants, embedding prewarm, repo registration, and Claude integration when eligible.

**Claude integration is conservative.** Shellbrain installs the repo-local Claude hook automatically only when the repo looks Claude-managed *and* `init` is running with a real Claude runtime signal. Otherwise it does nothing unless you pass `--host claude`.

When running Shellbrain from Codex Desktop or a similar tool shell, if direct calls fail in the current session, retry through a login shell first:

```bash
zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'
```

Then use the same wrapper shape for actual invocations if needed:

```bash
zsh -lc "source ~/.zprofile >/dev/null 2>&1; shellbrain read --json '{\"query\":\"Have we seen this migration lock timeout before?\",\"kinds\":[\"problem\",\"solution\",\"failed_tactic\"]}'"
```

If `doctor` reports `repair_needed`, rerun `shellbrain init`.

## Typical Workflow

1. Start with focused retrieval queries about the concrete problem, subsystem, constraint, or decision you are working on. Do not start with vague prompts like "what should I know about this repo?"
2. Use `read` again during the task whenever the search shifts or a memory might become useful midway through the work.
3. Before every evidence-bearing write, run `shellbrain events --json '{"limit":10}'` so you can inspect concrete `episode_event` ids.
4. At session end, normalize what happened into durable memories:
   - the `problem`
   - each `failed_tactic`
   - the `solution`
   - any durable `fact`, `preference`, or `change`
   - `utility_vote` updates for memories that helped or misled, using a `-1.0` to `1.0` scale where negative votes mean unhelpful and positive votes mean helpful

Never invent `evidence_refs`. If `events` returns nothing useful or the evidence is ambiguous, skip the write and try again later.

Use `--repo-root` when your current working directory is not the repo you want to target.

**Repo identity is remote-first.** Shellbrain prefers the normalized `origin` fetch URL. If `origin` is absent but there is exactly one remote, it uses that. If there are multiple remotes and none is `origin`, `init` stops and asks for `--repo-id`. If there is no usable remote, Shellbrain falls back to a weak-local identity tied to the current path.

## Backups and Recovery

Shellbrain exposes first-class logical backups:

```bash
shellbrain admin backup create
shellbrain admin backup list
shellbrain admin backup verify
shellbrain admin backup restore --target-db shellbrain_restore_001
shellbrain admin doctor
```

Backups default to `$SHELLBRAIN_HOME/backups`, which is `~/.shellbrain/backups` unless `SHELLBRAIN_HOME` is set. The Docker bind-mounted Postgres data dir protects against container loss, but it is not a backup strategy by itself.

## Advanced / Operator Notes

The normal product path should not require users to think about:

- raw DSNs
- manual `docker compose up`
- manual `shellbrain admin migrate`
- editable installs
- manual Claude hook edits

Those topics belong in the advanced/operator guide: [`docs/external-quickstart.md`](docs/external-quickstart.md)

## More

- Advanced/operator guide: [`docs/external-quickstart.md`](docs/external-quickstart.md)
- Session-start skill: [`skills/shellbrain-session-start/SKILL.md`](skills/shellbrain-session-start/SKILL.md)
