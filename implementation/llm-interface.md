# LLM Interface

Status: draft
Created: 2026-02-14

## Three Interfaces

### Read

- Ambient (conversation start): runtime runs `pack --query <prompt>`, injects result into system prompt. LLM doesn't decide this.
- Targeted (mid-task): LLM calls `search --query <q>` when it needs something specific.
- Below score threshold, return nothing. Empty results are correct, not errors.

### Write

- LLM calls `record-episode` when it observes something worth remembering.
- Must include evidence refs (user utterance, tool output, doc span). Unanchored writes are rejected.
- Write: user corrections, discovered facts, failed approaches, stated preferences.
- Don't write: transient state, obvious codebase facts, LLM's own uncertain inferences.

### Dispute

- LLM calls `dispute` against a specific card when it discovers a served memory is wrong.
- Triggers: user contradicts a preference, a fact is stale, a tactic fails.

## Score Thresholds

Returning nothing is better than returning noise.

- Global minimum score floor on all retrieval.
- `auto_pack` (ambient): stricter. Query is speculative.
- `search` (targeted): more permissive. LLM constructed the query from a specific need.
- `preference`: lower threshold. Getting preferences wrong is high-cost.
- `fact`: higher threshold. A wrong fact actively hurts.

## Bootstrap

The LLM learns the protocol from a system prompt injection provided by the runtime (hook/skill/MCP). The injection teaches: where memory lives, how to read/write/dispute, and that empty results mean proceed without memory.

## Open Questions

- Exact threshold values.
- Pack rendering format.
- Write payload simplification for LLM authoring.
- Multi-turn: re-pack per turn vs. first turn + targeted reads.
- Consolidation timing: sync vs. async.
