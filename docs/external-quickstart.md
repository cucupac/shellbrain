# External Quickstart

## Goal

Use Shellbrain from a normal agent session in a different repo.

Assume `shellbrain` is already available as a machine-level CLI from a one-time global install. Do not reinstall it per repo.

Think of Shellbrain as a case-based reasoning system:

- `read` retrieves durable memories that may help with the current problem
- `events` exposes episodic evidence from the current session
- `create` and `update` let the agent turn what happened into long-term structured memory

## One-Time Global Install

Preferred:

```bash
pipx install --editable /absolute/path/to/shellbrain
```

Fallback user-level editable install:

```bash
python3 -m pip install --user --break-system-packages --editable /absolute/path/to/shellbrain
export PATH="$(python3 -m site --user-base)/bin:$PATH"
```

For Codex Desktop and similar tool shells, put that PATH export and `SHELLBRAIN_DB_DSN` in `~/.zprofile`, not `~/.zshrc`, so non-interactive login shells can see them.

## Bootstrap

Set this once in your shell profile, then apply migrations:

```bash
export SHELLBRAIN_DB_DSN='postgresql+psycopg://shellbrain:shellbrain@localhost:5432/shellbrain'
shellbrain admin migrate
```

## Codex Startup Pattern

When running Shellbrain from Codex Desktop or a similar tool shell, treat this as the normal startup step:

```bash
zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'
```

Then use the same wrapper shape for real commands when needed:

```bash
zsh -lc "source ~/.zprofile >/dev/null 2>&1; shellbrain read --json '{\"query\":\"Have we seen this migration lock timeout before?\",\"kinds\":[\"problem\",\"solution\",\"failed_tactic\"]}'"
```

## Query First, But Query Precisely

Shellbrain `read` uses lexical retrieval plus semantic similarity. Query it with the concrete problem, subsystem, constraint, or decision you are working on. Do not start with vague prompts like "what should I know about this repo?"

Good first queries:

1. Prior attempts:

```bash
shellbrain read --json '{"query":"Have we seen this migration lock timeout before?","kinds":["problem","solution","failed_tactic"]}'
```

2. Constraints and preferences:

```bash
shellbrain read --json '{"query":"What repo constraints or user preferences matter for this auth refactor?","kinds":["fact","preference","change"]}'
```

3. Area-specific facts and changes:

```bash
shellbrain read --json '{"query":"What facts or recent changes matter around the payments retry worker?","kinds":["fact","change","problem","solution"]}'
```

The returned pack has:

- `direct`:
  direct matches
- `explicit_related`:
  linked memories
- `implicit_related`:
  semantic neighbors and associative hops

Query again whenever the search shifts or a memory might become useful mid-journey.

## Session Protocol

1. Use focused `read` queries to pull relevant prior cases, facts, and preferences.
2. Solve the problem normally. Shellbrain's background episodic capture keeps transcript evidence up to date.
3. Before every evidence-bearing write, inspect fresh evidence:

```bash
shellbrain events --json '{"limit":10}'
```

4. Use returned `episode_event` ids verbatim in `create` or any evidence-bearing `update`.
5. At session end, normalize what happened into durable memories.

Examples:

```bash
shellbrain create --json '{"memory":{"text":"Migration failed because the lock timeout was too low","kind":"problem","evidence_refs":["evt-123"]}}'
shellbrain create --json '{"memory":{"text":"Increasing lock_timeout to 30s fixed the migration","kind":"solution","links":{"problem_id":"mem-problem-123"},"evidence_refs":["evt-124"]}}'
shellbrain create --json '{"memory":{"text":"Retrying the migration without changing the timeout failed again","kind":"failed_tactic","links":{"problem_id":"mem-problem-123"},"evidence_refs":["evt-125"]}}'
shellbrain update --json '{"memory_id":"mem-older-solution","update":{"type":"utility_vote","problem_id":"mem-problem-123","vote":1.0,"rationale":"This prior fix led directly to the right timeout change.","evidence_refs":["evt-126"]}}'
```

## What To Store

- `problem`:
  the obstacle or failure mode
- `solution`:
  what worked for that problem
- `failed_tactic`:
  what did not work for that problem
- `fact`:
  durable truth about the repo, environment, or architecture
- `preference`:
  durable user or repo convention
- `change`:
  something that invalidated prior truth

Use `update` for:

- `utility_vote`:
  whether a memory helped with a specific problem on a `-1.0` to `1.0` scale
  negative = unhelpful or misleading
  `0.0` = neutral or unclear
  positive = helpful
- `fact_update_link`:
  connecting old and new facts through a `change`
- `association_link`:
  explicit durable relationships between memories
- `archive_state`:
  hiding or restoring an existing memory

When truth changed, the semantic-memory pattern is:

1. create a `change`
2. create the new `fact`
3. connect old and new facts with `fact_update_link`

## Scope and Hierarchy

- Most memories should stay repo-scoped.
- Use `scope: "global"` for cross-repo user preferences, coding-style preferences, or project facts that are not tied to one repo.

## Rules

- Never invent `evidence_refs`.
- Skip the write if evidence is missing or ambiguous.
- `solution` and `failed_tactic` require `links.problem_id`.
- `archive_state` does not use `evidence_refs`; the evidence-bearing update types carry them inside the `update` object.

## Repo Targeting

- `--repo-root` targets a repo even when your shell is elsewhere.
- `--repo-id` overrides the default `basename(repo_root)` inference.

Example:

```bash
shellbrain --repo-root /path/to/other-repo read --json '{"query":"What repo conventions matter here?","kinds":["fact","preference","change"]}'
```

## Codex Skill

This repo ships a versioned session-start skill at [`skills/shellbrain-session-start/SKILL.md`](../skills/shellbrain-session-start/SKILL.md).

To use it in Codex, copy or symlink the directory into `$CODEX_HOME/skills`:

```bash
mkdir -p "$CODEX_HOME/skills"
ln -s /absolute/path/to/shellbrain/skills/shellbrain-session-start "$CODEX_HOME/skills/shellbrain-session-start"
```
