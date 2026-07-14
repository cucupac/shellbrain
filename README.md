<p align="center">
  <img src="https://raw.githubusercontent.com/cucupac/shellbrain/main/docs/assets/shellbrain_logo_badge.png" alt="ShellBrain logo" height="88">
</p>

<h3 align="center">ShellBrain</h3>

<p align="center">Long-term Memory for AI Agents.</p>

Agents forget across sessions. They rediscover the same problems, repeat the same mistakes, and relearn what you already taught them. **ShellBrain makes their work compound.**

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

## Recall in one command.
Episodic, empirical, conceptual. Three categories, one retrieval surface.

---

## Architecture

**Episodic knowledge** is the _evidence_ layer.
- What actually happened in the session: your prompts, the agent's steps, tool calls, and outputs.

**Empirical knowledge** is the concrete _extracted_ layer.
- An ontology of problems, solutions, failed tactics, facts, preferences, changes.
- This is **case-based reasoning** in a semantic graph.

**Conceptual knowledge** is the _abstractive_ layer.
- A **higher-level concept graph** with claims, relations, and implementations that link back to the concrete layer.
- **Progressive disclosure.** agents get oriented first, then ask for depth only where tasks require it.

The episodic layer is truth. Empirical memory extracts. Concept memory abstracts. **Each layer is grounded in the one beneath it.**

---

## How Agents Use ShellBrain

### Recall

**Working agents call `shellbrain recall`.** That is the normal interface they have to think about. One command, **one _carefully curated_ compact brief** for the task at hand.

Recall receives only the quoted query, so include the relevant task, failure, subsystem, or decision naturally in the question.

```bash
shellbrain recall "What is ShellBrain, and how does it help a working coding agent?"
```

Response shape:

```json
{
  "status": "ok",
  "data": {
    "brief": {
      "summary": "...",
      "constraints": ["..."],
      "known_traps": ["..."],
      "prior_cases": ["..."],
      "concept_orientation": ["..."],
      "anchors": ["`README.md`"],
      "conflicts": ["..."],
      "gaps": ["..."],
      "next_checks": ["..."]
    },
    "fallback_reason": null
  },
  "errors": []
}
```

**Working agents focus on only their work.**

### Teach

**Working agents call `shellbrain teach` for explicit teaching.** You can tell an agent to remember important ideas.

---

## Principled and Disciplined

Memory that is grounded in evidence, small in scope, and asked for rather than pushed is memory that compounds. Everything else is noise for working agents.

**A memory layer that cannot justify itself should not persist.**

---

## How to Use ShellBrain

Use Shellbrain in your agent of choice. Then, just work normally.

**Claude Code:** *Use `/shellbrain` to remember Shellbrain recall at the right task boundaries.*

**Codex:** *Use $shellbrain to remember Shellbrain recall at the right task boundaries.*

**Cursor:** *Use `/shellbrain` to remember Shellbrain recall at the right task boundaries.*

---

## Repair

`shellbrain admin doctor` to inspect. `shellbrain init` to repair if doctor flags it. Do not rerun init every session.

---

## Docs

- [For Humans](https://shellbrain.ai/humans/) — install, upgrade, getting started
- [For Agents](https://shellbrain.ai/agents/) — agent workflow and write discipline
- [Technical Docs](https://deepwiki.com/cucupac/shellbrain) — in-depth generated docs and codebase map
