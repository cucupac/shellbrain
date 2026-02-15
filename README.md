# Memory System (Plan C Phases 1-5)

This repository now includes a runnable local implementation in:

- `/Users/example/memory/memory_cli.py`

It implements:

- Phase 1: append-only `episodes`, `artifacts`, `evidence_refs`, `memory_events`
- Phase 2: deterministic consolidation into `cards` + event-backed ledger
- Phase 3: retrieval/search, deterministic packing, persisted snapshots, exposures
- Phase 4: dispute/lifecycle state transitions, outcomes, utility attribution
- Phase 5: operational hardening (`status`, recovery, full rebuild, idempotency checks, embedding migration, gates)

## Quick start

```bash
python3 /Users/example/memory/memory_cli.py --db /Users/example/memory/.memory/demo.db init
```

## Core commands

```bash
python3 /Users/example/memory/memory_cli.py --db <db> record-episode --input <episode.json>
python3 /Users/example/memory/memory_cli.py --db <db> consolidate --episode <episode_id>
python3 /Users/example/memory/memory_cli.py --db <db> search --episode <episode_id> --query "..."
python3 /Users/example/memory/memory_cli.py --db <db> pack --episode <episode_id> --query "..." --channel auto_pack
python3 /Users/example/memory/memory_cli.py --db <db> record-outcome --episode <episode_id> --type tool_success --evidence-ref-ids <ev1,ev2>
python3 /Users/example/memory/memory_cli.py --db <db> record-dispute --episode <episode_id> --card-id <card_id> --evidence-ref-id <ev_id>
python3 /Users/example/memory/memory_cli.py --db <db> explain-pack --episode <episode_id>
python3 /Users/example/memory/memory_cli.py --db <db> explain-consolidation --episode <episode_id>
python3 /Users/example/memory/memory_cli.py --db <db> replay
python3 /Users/example/memory/memory_cli.py --db <db> status --days 30
python3 /Users/example/memory/memory_cli.py --db <db> recover
python3 /Users/example/memory/memory_cli.py --db <db> verify-idempotency --sample-events 200
python3 /Users/example/memory/memory_cli.py --db <db> full-rebuild --verify-stability
python3 /Users/example/memory/memory_cli.py --db <db> migrate-embeddings --to-model pseudo-v2 --from-model pseudo-v1
python3 /Users/example/memory/memory_cli.py --db <db> gates --days 30
```

## Example input

A working example payload is included at:

- `/Users/example/memory/examples/episode1.json`

## Notes

- Event writes are idempotent via `idempotency_key`.
- Reducers are replayable from `memory_events`.
- Card retrieval and packing are deterministic with fixed tie-break rules.
- `verify-idempotency` validates replay stability and idempotent append behavior against sampled events.
