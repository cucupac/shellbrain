<p align="center">
  <img src="https://raw.githubusercontent.com/cucupac/shellbrain/main/docs/assets/shellbrain_logo_badge.png" alt="ShellBrain logo" height="88">
</p>

<h3 align="center">ShellBrain</h3>

<p align="center">Long-term Memory for AI Agents.</p>

ShellBrain uses case-based reasoning and a self-managing concept graph as long-term memory for software engineering.

## Install

```bash
curl -L shellbrain.ai/install | bash
```

**Works for Codex, Claude Code, and Cursor.**

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

Memories and concepts link directly to supporting evidence. The code is the source of truth.

---

## How Agents Use ShellBrain

### Recall

Working agents run `shellbrain recall` for long-term memory related to their current task.

Recall combines BM25, vector similarity, and explicit graph associations--and then summarizes using an LLM.

```bash
shellbrain recall "What is ShellBrain, and how does it help a working coding agent?"
```

**Response:**

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

If there are no relevant memories, nothing is returned.

### Recall Provider

For blazing fast recall for cheap, [get an Inception API key](https://platform.inceptionlabs.ai/dashboard/api-keys) and run:

```bash
mkdir -p ~/.shellbrain
printf '\nINCEPTION_API_KEY=%s\n' 'PASTE_YOUR_KEY_HERE' >> ~/.shellbrain/.env
chmod 600 ~/.shellbrain/.env
shellbrain admin recall provider inception
```

Switch back with `shellbrain admin recall provider codex`, or choose `claude`.

---

## Docs

- [For Humans](https://shellbrain.ai/humans/): installation, upgrades, and first steps
- [For Agents](https://shellbrain.ai/agents/): agent workflow and memory rules
- [Technical Docs](https://deepwiki.com/cucupac/shellbrain): detailed documentation and code map
