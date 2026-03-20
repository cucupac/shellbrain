# Building a Brain

`shellbrain` is a machine-level CLI that gives agent sessions repo-scoped long-term memory.

It stores durable memories like `problem`, `solution`, `fact`, and `preference`, grounded by transcript-derived evidence from the active host session.

## Install

Primary install path:

```bash
curl -L shellbrain.ai/install | bash
```

The installer already runs `shellbrain init` for you.

That makes the machine ready immediately, installs the Codex and Claude integrations, and lets repos register themselves later on first real Shellbrain use.

Manual install path:

```bash
pipx install shellbrain
shellbrain init
```

## What Install Does

- installs the `shellbrain` CLI once per machine
- provisions or reuses the managed local runtime on first `init`
- installs the personal Codex skill
- installs the personal Claude skill
- installs the Claude global SessionStart hook in `~/.claude/settings.json`
- auto-registers repos later on first use inside a repo

If readiness is unclear after install, run:

```bash
shellbrain admin doctor
```

If `doctor` reports `repair_needed`, rerun:

```bash
shellbrain init
```

## First Useful Command

From inside a repo, start with a concrete retrieval query:

```bash
shellbrain read --json '{"query":"Have we seen this failure mode before?","kinds":["problem","solution","failed_tactic"]}'
```

If direct calls fail in a tool shell, retry through a login shell first:

```bash
zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'
```

## More

- Advanced/operator guide: [`docs/external-quickstart.md`](docs/external-quickstart.md)
- Codex session-start skill: [`skills/shellbrain-session-start/SKILL.md`](skills/shellbrain-session-start/SKILL.md)
