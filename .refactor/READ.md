## Summary

This refactor moves Shellbrain toward the finalized clean-core architecture: CLI entrypoints only parse, hydrate, call startup-wired handlers, present, and return exit codes; handlers own command context, telemetry attachment, result envelopes, session evidence hydration, and audience-shaped responses; startup becomes the composition root for concrete dependencies; core is limited to entities, contracts, ports, policies, and typed use cases over ports; infrastructure owns concrete database, filesystem, process, host, telemetry capture, reporting, runtime, and PostgreSQL mechanics. The work must preserve behavior while deleting old paths instead of adding compatibility shims, and each chunk must record importer discovery, move tests with source, pass its gate, and survive actor-critic review.

## Ambiguities

- Chunk 1 says guardrails are expected to fail until later chunks land, while the general per-chunk gate says acceptance criteria pass. I will treat Chunk 1 as passing when the new tests fail only for baseline-known violations and are not weakened to go green prematurely.
- The plan requires subagents for parallel discovery and chunk work. I will use bounded subagent reports for discovery and critic review, then keep mutations in the chunk owner’s workspace with import updates in the same chunk.
- "Current focused and non-Docker test suites" is not named as one fixed command in the plan. I will discover the repo’s existing commands and record exactly which commands were run in `.refactor/baseline/`.
- Parser splitting is explicitly secondary. I will only split parser files if protocol or handler wiring makes that necessary.

## Execution Plan

1. Chunk 0: capture baseline `git status --short`, `tree -L 4 app`, import maps for planned move targets, and current focused/non-Docker test results; no source moves.
2. Chunk 1: add strict architecture guardrail tests that initially identify only baseline-known violations.
3. Parallel set: run Chunks 2, 3, 4, and 5 as independent chunk owners after Chunk 1, each with discovery, mutation, verification, and critic signoff; then run a merged guardrail suite.
4. Chunk 6: implement handlers and startup handler wiring sequentially, with at least two critic rounds.
5. Parallel set: run Chunks 7 and 8 independently after Chunk 6, then verify the full done checklist.
6. Closeout: run final guardrails, focused suites, non-Docker suite, `ruff check .`, `git diff --check`, write `.refactor/REPORT.md`, and only declare done if every required item is green or a root `BLOCKER.md` exists.
