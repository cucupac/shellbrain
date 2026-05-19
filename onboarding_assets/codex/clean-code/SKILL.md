---
name: clean-code
description: "Clean existing code by enforcing semantic integrity, reader clarity, and local efficiency without changing architecture. Use when auditing or improving code that has fake optionality, silent fallbacks, stale compatibility, permissive parsing, unclear names, dead wrappers, redundant work, or over-abstraction. Prefer required typed state, explicit errors, fail-fast validation, deletion of obsolete branches, clear names, simple functions, and focused tests."
---

# Clean Code

Clean code is code whose meaning is truthful, visible, and efficient enough for its job.

This skill answers:

> Is this code honest about what states are valid, clear about what it does, and free of needless local complexity?

Use `clean-architecture` for responsibility placement, dependency direction, structural stage, startup wiring, adapters, and core boundaries. Use `clean-code` to evaluate the code inside those boundaries.

## Priority Order

Apply checks in this order:

1. Semantic integrity
2. Reader clarity
3. Local efficiency

Do not polish unclear code before deciding whether the behavior should exist. Do not optimize code whose meaning is wrong. Do not rename or compress code in ways that hide invariants.

## Semantic Integrity

Semantic integrity is the hard gate.

Fail code that makes invalid, obsolete, missing, or unknown state look acceptable.

Look for:

- `Option<T>` where absence is invalid
- `Result<Option<T>>` where missing should be an error
- nullable fields that are required in real usage
- defaults hiding bad config or bad data
- silent fallbacks
- legacy aliases
- permissive parsing of old formats
- multiple schemas accepted in normal runtime paths
- null, zero, empty, or infinity sentinels standing in for real meaning
- invalid state converted to `None`, `0`, empty list, default object, or best-effort skip
- swallowed errors around required behavior
- broad enums with unused variants
- boolean flags that hide real states
- stringly typed domain or config values
- `HashMap<String, Value>` or untyped blobs where the current shape is known
- generic traits or interfaces with one real implementation
- plugin-like abstractions with no real plugin use
- compatibility wrappers after callers migrated
- runtime env reads instead of startup validation
- migration or legacy logic in hot runtime paths
- tests that preserve obsolete behavior instead of current canonical behavior

Prefer:

- one canonical behavior
- required typed state
- explicit invariants
- explicit errors
- fail-fast validation
- startup-owned config parsing
- deletion over compatibility
- migration or preflight tooling outside runtime paths
- negative tests proving old behavior fails

Ask before accepting a fallback, option, default, alias, parser mode, or abstraction:

1. What invariant should hold here?
2. What decision is this code avoiding?
3. What behavior is actually required today?
4. What old or invalid behavior is being kept alive?
5. Can the obsolete path be deleted?
6. Can the remaining behavior be required, typed, and validated?
7. What test, grep, caller check, deploy check, data scan, metric, or empirical check makes deletion safe?

## Reader Clarity

Improve code so the intended behavior is visible.

Check:

- Does each function do one thing?
- Can its summary be one accurate sentence without hiding multiple responsibilities?
- Does its name describe purpose or result, not mechanism?
- Do parameter and local names reveal domain meaning instead of storage shape or plumbing?
- Does orchestration read like a clear flow?
- Are helpers close to the code they support?
- Are wrappers, managers, processors, services, and utils hiding simple behavior?
- Are comments explaining why, not restating what?
- Can a reader find the main path quickly?

Prefer the formulation that makes intent most visible. Clever is not clean.

## Local Efficiency

Remove needless local work when behavior is preserved.

Check:

- repeated scans
- avoidable allocations
- recomputed invariants inside loops
- repeated parsing
- needless clones or copies
- throwaway collections
- duplicate conversions caused by poor local boundaries

Do not micro-optimize. Do not trade clarity for cleverness. Use profile-guided intuition when performance risk is not obvious.

## Commit Gate Review

For commit-gate review, classify findings as:

- **Blocker:** semantic integrity violation introduced or preserved in touched code.
- **Should fix:** unclear names, redundant wrappers, dead local code, duplicated logic, or avoidable local work in touched code.
- **Optional:** minor readability or efficiency cleanup outside the changed behavior.

A commit should fail the clean-code gate if it introduces or preserves in touched code:

- fake optionality
- silent fallback
- stale compatibility
- permissive parsing
- invalid state disguised as valid state
- broad abstraction with no current use
- swallowed errors around required behavior

A commit should not fail solely for unrelated old code outside the diff unless the touched code depends on it directly.

## Implementation Workflow

When fixing clean-code issues:

1. Identify the current invariant.
2. Identify obsolete or invalid behavior.
3. Add or update tests before tightening behavior when risk is non-trivial.
4. Delete obsolete branches or fallbacks.
5. Make required state required and typed.
6. Rename and simplify only after the behavior is correct.
7. Remove redundant local work.
8. Run focused tests and checks.
9. Report behavior changes separately from behavior-preserving cleanup.

Do not bundle unrelated semantic changes. A commit should remove or enforce one coherent behavior.

## Config And Env

Configuration semantics should be decided at startup.

Prefer:

- one canonical env var per concept
- typed startup settings
- explicit missing-var errors
- explicit conflict errors when old and new aliases are both present
- tests for required config and alias rejection

Avoid:

- reading env vars in business logic
- accepting legacy aliases indefinitely
- fallback defaults for required production config
- stringly typed mode or config flags
- runtime switches where startup validation should decide

## Data And Schema

Runtime code should not quietly survive bad persisted data.

Prefer:

- typed read-boundary validation
- non-mutating preflight scanners for live data cleanup
- explicit migration or remediation tooling
- clear errors for malformed rows
- schema compatibility isolated to adapters or migration paths

Avoid:

- silent row skips
- defaulting malformed DB, Redis, cache, or file fields
- dual-read logic in hot paths after migration is complete
- editing applied migrations destructively
- treating old persisted shapes as current domain truth

## Performance-Sensitive Behavior

For routing, quote, optimizer, benchmark, money, ranking, capacity, or other performance-sensitive behavior, semantic cleanup must preserve empirical behavior unless intentionally changed.

Before deleting fallback behavior, record the protected invariants.

Examples:

- quote errors must not become zero quotes
- missing gas must not become free gas
- invalid capacity must not become unbounded capacity
- benchmark fake modes must remain explicit test or benchmark behavior
- optimizer eligibility must not silently drop
- snapshot identity and cache invalidation must remain correct

Use empirical checks when behavior can affect ranking, optimizer inclusion, active-set support, benchmark results, money movement, or production safety.

## Relationship To Other Skills

Use `clean-architecture` when deciding where code belongs.

Use `clean-code` when deciding whether code is truthful, clear, and locally efficient.

Use domain-specific skills after `clean-code` when the domain has extra invariants or empirical gates.

Do not use `clean-code` as a license for broad refactor sprees. The goal is stricter meaning and clearer expression, not churn.

## Output

For an audit, return:

- highest-risk clean-code issues
- obsolete behavior to delete
- required typed state to introduce
- fallbacks or defaults to remove
- validation that should move earlier
- readability or local efficiency fixes worth doing
- tests or checks needed before tightening

For an implementation plan, return:

- invariant
- old behavior removed
- new canonical behavior
- likely files or modules involved
- tests to add or update
- checks to run
- commit boundaries

For a commit-gate review, return:

- pass or fail
- blocking semantic issues
- should-fix readability or efficiency issues
- optional cleanup suggestions
- whether any compatibility, optionality, or fallback behavior was introduced
