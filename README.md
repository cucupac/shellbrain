<p align="center">
  <img src="https://raw.githubusercontent.com/cucupac/shellbrain/main/docs/assets/shellbrain_logo_badge.png" alt="ShellBrain logo" height="88">
</p>

<h3 align="center">ShellBrain</h3>

<p align="center">Long-term Memory for AI Agents.</p>

ShellBrain carries useful lessons from one agent task to the next. It preserves decision reasons, failed approaches, product direction, and preferences that the resulting code does not explain.

## Install

```bash
curl -L shellbrain.ai/install | bash
```

**Works for Codex, Claude Code, and Cursor.** The installer configures the runtime automatically. Repos register themselves on first use.

Requirements.
- macOS or Linux, Python 3.11+, Docker for the managed local Postgres+pgvector runtime.

### Upgrade for latest capabilities

```bash
shellbrain upgrade
```

You can also run `curl -L shellbrain.ai/upgrade | bash`.

---

## Recall in one command

<p align="center">
  <img src="docs/assets/shellbrain-recall-context-diagram.png" alt="ShellBrain recall uses vector search and BM25 to search your memories. An inner recall agent summarizes the search results." width="720">
</p>

---

## Architecture

ShellBrain stores evidence and two forms of reusable knowledge:

- **Episodic knowledge records evidence.** It stores prompts, agent steps, tool calls, and outputs from each session.
- **Empirical knowledge extracts concrete memories.** It organizes problems, solutions, failed tactics, facts, preferences, and changes in a semantic graph for **case-based reasoning**.
- **Conceptual knowledge abstracts reusable ideas.** Its concept graph connects claims, relations, and implementations to empirical knowledge.

Memories and concept claims link to supporting evidence. A concept can express a product principle without a duplicate memory. Current code remains the source of truth for implementation details.

---

## How Agents Use ShellBrain

### Recall

Working agents run `shellbrain recall` to get one compact brief for the current task.

Recall and automatic learning use the same evidence selector. It combines BM25, vector similarity, and graph links. Learning agents receive the selected records. The recall agent can summarize them.

Recall receives only the quoted query. Include the relevant task, failure, subsystem, or decision in the question.

```bash
shellbrain recall "What is ShellBrain, and how does it help a working coding agent?"
```

**Response format:**

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

Recall selects an evidence pack in code, then asks an inner agent to summarize it. Source attribution comes from the selected records. Provider failures return a brief directly from that same pack.

### Recall provider

Codex is the default. Choose one provider for recall across repositories:

```bash
shellbrain admin recall provider inception
shellbrain admin recall provider codex
shellbrain admin recall provider claude
```

For faster recall with Mercury, set your Inception API key and select Inception:

```bash
export INCEPTION_API_KEY="your-inception-api-key"
shellbrain admin recall provider inception
```

Start your agent host with that environment. `.env` files are not loaded automatically. Automatic memory building is unchanged.

Selection is stored in `~/.shellbrain/recall-provider.toml` (or under `SHELLBRAIN_HOME`). API failures return deterministic context with failure metadata. The API uses a 10-second socket timeout and no automatic retries; a slowly trickling response can exceed that elapsed time.

---

## Memory Discipline

ShellBrain keeps memory grounded in evidence and narrow in scope. Agents request memory when they need it.

**Memory that cannot justify itself should not persist.**

---

## Use ShellBrain

Use Shellbrain with your preferred agent. Then work as usual.

- **Claude Code:** Use `/shellbrain` to recall context at task boundaries.
- **Codex:** Use $shellbrain to recall context at task boundaries.
- **Cursor:** Use `/shellbrain` to recall context at task boundaries.

---

## Repair

Run `shellbrain upgrade` to repair an existing installation. Setup and schema migrations run automatically.

---

## Docs

- [For Humans](https://shellbrain.ai/humans/): installation, upgrades, and first steps
- [For Agents](https://shellbrain.ai/agents/): agent workflow and memory rules
- [Technical Docs](https://deepwiki.com/cucupac/shellbrain): detailed documentation and code map
