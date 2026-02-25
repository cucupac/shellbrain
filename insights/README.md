# Insights Folder

This folder captures evolving design decisions for the memory system.

## Structure

Canonical organization:
- `00-lab/`: raw, append-only working notes while ideating.
- `discovery.md`: append-only chronology and cross-links.
- `01-foundation/`: baseline architecture and ontology.
- `02-breakthrough/`: raw and structured breakthrough ideation.
- `03-refinements/`: later policy notes and verbatim refinements.
- `04-contracts/`: concrete interface contracts and schema cards.
- `05-ratified/`: current ratified-state register that resolves doc drift by favoring newer ratified decisions.
- `06-working-set/`: implementation-focused spec pack (current locked state by subsystem + open items).

Naming convention:
- Directory prefix is stage (`00`, `01`, `02`, `03`, `04`).
- Files inside each directory keep human-readable semantic names.

## Working Rule For Agents

Always take notes without waiting for explicit user instruction when memory-design ideas evolve.

Two-layer logging is required:
- Layer 1 (raw): append to `00-lab/immutable-work-log.md`.
- Layer 2 (abstraction): append distilled outcomes to `discovery.md` only after explicit user approval.

Ratification gate:
- Entries in `00-lab/immutable-work-log.md` are draft ideation by default.
- Do not promote draft ideation into `discovery.md` without explicit user approval in the conversation.
- `discovery.md` should contain ratified decisions, policy shifts, or approved open-question clusters.

Use append-only history:
- Do not rewrite prior entries unless correcting factual errors.
- Add a new dated entry with what changed, why it changed, and what is still open.
- Reference the exact files that were added or updated in that step.

Raw log format (concise):
- Timestamp.
- What was proposed.
- What seemed to work.
- What seemed not to work.
- Open questions.
- Files touched.

## Discovery Log

Primary chronology file: `discovery.md`

Current ratified-state digest:
- `05-ratified/ratified-state-register-v1.md`

Current implementation working set:
- `06-working-set/README.md`
