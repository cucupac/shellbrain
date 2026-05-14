<p align="center">
  <img src="https://raw.githubusercontent.com/cucupac/shellbrain/main/docs/assets/shellbrain_logo_badge.png" alt="ShellBrain logo" height="88">
</p>

<h3 align="center">ShellBrain</h3>

<p align="center">Long-term Memory for AI Agents.</p>

Agents forget across sessions. They rediscover the same problems, repeat the same mistakes, and relearn what you already taught them. **ShellBrain makes their work compound.**

### Recall in one command.
Episodic, empirical, conceptual. Three categories, one retrieval surface.

---

## Architecture

**Episodic knowledge** is the _evidence_ layer.
- What actually happened in the session: your prompts, the agent's steps, tool calls, and outputs.

**Empirical knowledge** is the concrete _extracted_ layer.
- An ontology of problems, solutions, failed tactics, facts, preferences, changes.
- This is **case-based reasoning** in a semantic graph.

**Conceptual konwledge** is the _abstractive_ layer.
- A **higher-level concept graph** with claims, relations, and implementations that link back to the concrete layer.
- **Progressive disclosure.** agents get oriented first, then ask for depth only where tasks require it.

The episodic layer is truth. Empirical memory extracts. Concept memory abstracts. **Each layer is grounded in the one beneath it.**

---

## How agents use ShellBrain

**Working agents call `recall`.** That is the entire interface they have to think about. One command, **one _carefully curated_ compact brief**, with sources cited.

```bash
shellbrain recall --json '{"query":"what context matters for this migration lock timeout?","current_problem":{"goal":"fix the migration hang","surface":"db admin","obstacle":"lock timeout","hypothesis":"none yet"}}'
```

Lower-level commands exist for inner agents.
- `read`, `events`, `concept show`, `memory add`, `memory update`, `concept add`, `concept update`

**Working agents focus on only their work.**

---

## Principled and Disciplined

Memory that is grounded in evidence, small in scope, and asked for rather than pushed is memory that compounds. Everything else is noise for working agents.

**A memory layer that cannot justify itself should not persist.**

---

## Install

```bash
curl -L shellbrain.ai/install | bash
```

**Works for Codex, Claude Code, and Cursor.** The installer runs `shellbrain init` for you. Repos register themselves on first use.

Requirements.
- macOS or Linux, Python 3.11+, Docker for the managed local Postgres+pgvector runtime.

### Upgrade for latest capabilities

```bash
shellbrain upgrade
```

The install script also works as an upgrade path: `curl -L shellbrain.ai/upgrade | bash`. Manual alternative: `pipx upgrade shellbrain && shellbrain init`.

---

## Use it

Use Shellbrain Session Start in your agent of choice. Then, just work normally.

**Claude Code:** *Use `/shellbrain-session-start` to get up to speed in this repo and record durable evidence-backed learnings.*

**Codex:** *Use $shellbrain-session-start to get up to speed in this repo and record durable evidence-backed learnings.*

**Cursor:** *Use `/shellbrain-session-start` to get up to speed in this repo and record durable evidence-backed learnings.*

---

## Repair

`shellbrain admin doctor` to inspect. `shellbrain init` to repair if doctor flags it. Do not rerun init every session — it is not a no-op.

---

## Docs

- [shellbrain.ai/humans](https://shellbrain.ai/humans/) — install, upgrade, getting started
- [shellbrain.ai/agents](https://shellbrain.ai/agents/) — agent workflow and write discipline
- [shellbrain.ai/recall](https://shellbrain.ai/recall/) — retrieval pipeline
- [shellbrain.ai/memory/episodic](https://shellbrain.ai/memory/episodic/) — transcript evidence
- [shellbrain.ai/memory/semantic](https://shellbrain.ai/memory/semantic/) — facts, preferences, changes
- [shellbrain.ai/memory/procedural](https://shellbrain.ai/memory/procedural/) — problems, solutions, failed tactics
- [shellbrain.ai/memory/associative](https://shellbrain.ai/memory/associative/) — explicit links and semantic neighbors
