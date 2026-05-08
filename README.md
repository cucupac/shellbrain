# Building a Brain

**Shellbrain gives agent sessions repo-scoped long-term memory.**
It stores what happened, what worked, what failed, and what the human prefers — then retrieves the relevant pieces the moment a similar problem surfaces. *Every session compounds into the next.*

---

## Install

```bash
curl -L shellbrain.ai/install | bash
```

**One command on supported machines.** The installer provisions the local runtime, installs the Codex, Claude, and Cursor skills, wires the Claude SessionStart hook, and runs `shellbrain init` for you. On first bootstrap, `shellbrain init` asks how it should store data. Repos register themselves on first use.

**Requirements**

- macOS or Linux
- Python 3.11+ required
- `shellbrain init` asks you to choose one storage mode on first bootstrap
- managed local: Docker installed and the daemon running
- external: PostgreSQL with pgvector
- first init downloads a local embedding model
- Windows is not supported yet

---

## Upgrade

```bash
shellbrain upgrade
```

**Upgrades the package and reruns init.** Skills, hooks, and the managed runtime all refresh in one pass.

The install script also works as an upgrade path — `curl -L shellbrain.ai/upgrade | bash` if you prefer. Manual alternative: `pipx upgrade shellbrain && shellbrain init`.

---

## Use it

**You use shellbrain by launching a skill in your agent.**

**Codex:** `Use $shellbrain-session-start to get up to speed in this repo with shellbrain and record durable evidence-backed learnings.`

**Claude Code:** `Use Shellbrain Session Start to get up to speed in this repo with shellbrain and record durable evidence-backed learnings.`

**Cursor:** `Use shellbrain-session-start to get up to speed in this repo with shellbrain and record durable evidence-backed learnings.`

The agent handles everything from there — reading prior context, gathering evidence, writing durable memories at session end. *You don't manage any of this directly.*

---

## Four operations

**`read`** retrieves durable memories related to a concrete problem. Re-run whenever the search shifts.

**`events`** syncs the active transcript. Returns episode event ids to cite as evidence. Run before every write.

**`memory add`** writes one durable memory. At least one evidence reference required.

**`memory update`** records utility votes, truth-evolution links, explicit associations, or archive state.

The rhythm: `read` first, `events` before writes, `memory add`/`memory update` at session end. *Do not rerun `shellbrain init` every session.*

---

## Repair

**`shellbrain admin doctor`** is the inspect path when something feels wrong.

**`shellbrain init`** is the repair path if doctor says `repair_needed`. The installer already ran it once — you only rerun it to fix things.

If `shellbrain` isn't found in a tool shell, retry through the shell-specific path the installer configured:

```bash
zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'
bash -lc 'source ~/.bash_profile >/dev/null 2>&1; shellbrain --help'
```

Fish PATH setup is written to `~/.config/fish/conf.d/shellbrain.fish`.

---

## DB-backed tests

**Live memories and DB-backed tests now use different Postgres hosts.**

- managed local Shellbrain keeps durable memories on the machine-owned managed instance
- DB-backed tests and scratch validation should use the dedicated repo-owned test host from `docker-compose.test.yml`
- `scripts/run_tests` provisions a disposable test database on that dedicated host by default
- `scripts/storage_status` shows the live managed target, the dedicated test host, and any legacy local test host that is still hanging around

If you are running managed local Shellbrain, do not leave a stale `SHELLBRAIN_DB_DSN` export in your shell profile that points at the old local compose database. The machine config wins anyway, and the stale env var just makes the storage layout harder to reason about.

---

## Docs

- [shellbrain.ai/humans](https://shellbrain.ai/humans/) — install, upgrade, getting started
- [shellbrain.ai/agents](https://shellbrain.ai/agents/) — how agents use shellbrain, with a sitemap to every page
- [shellbrain.ai/recall](https://shellbrain.ai/recall/) — how the read pipeline works
