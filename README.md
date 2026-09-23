<p align="center">
  <img src="https://raw.githubusercontent.com/cucupac/shellbrain/main/docs/assets/shellbrain_logo_badge.png" alt="ShellBrain logo" height="88">
</p>

<h3 align="center">ShellBrain</h3>

<p align="center">Long-term Memory for AI.</p>

ShellBrain uses case-based reasoning and a self-managing concept graph as long-term memory for software engineering.

## Install

```bash
curl -L shellbrain.ai/install | bash
```

**Works for Codex, Claude Code, and Cursor.**

Requirements.
- macOS or Linux, Python 3.11+, Docker.

### Upgrade for Latest Capabilities

```bash
shellbrain upgrade
```

---

## Recall in One Command

<p align="center">
  <img src="docs/assets/shellbrain-recall-context-diagram.png" alt="ShellBrain recall uses vector search and BM25 to search your memories. An inner recall agent summarizes the search results." width="720">
</p>

---

## Architecture

ShellBrain stores evidence and two forms of reusable knowledge:

- **Episodic Memory.** It stores prompts, responses, and tool calls.
- **Case-Based Memory.** Problems, solutions, and failed attempts are structured and stored.
- **Concept Graph.** It connects claims, relations, and implementations.

Memories and concepts link directly to supporting evidence. The code is the source of truth.

---

## How Agents Use ShellBrain

### Recall

Working agents run `shellbrain recall` for long-term memory related to their current task.

Recall combines BM25, vector similarity, and explicit graph associations.

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

Tune recall in `~/.shellbrain/recall.yaml` (optional; these are the defaults):

```yaml
recall:
  max_memories: 12
  max_concepts: 4
  max_neighbor_concepts: 2
  max_claims_per_concept: 3
  max_groundings_per_concept: 2
  max_input_tokens: 8000
```

The input budget uses a byte-based token estimate. Settings affect recall synthesis only.


---

## Docs

- [Technical Docs](https://deepwiki.com/cucupac/shellbrain)
