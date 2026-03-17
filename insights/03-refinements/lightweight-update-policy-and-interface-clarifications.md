# Lightweight Update Policy and Interface Clarifications

Captured from ratified portions of the 2026-02-18 conversation.

## 1) Anti-rigidity principle

- Avoid rigid update taxonomies (for example, fixed labels like supports/contradicts/helpful/harmful/irrelevant).
- Keep the system behavioral and lightweight: shellbrain is optional utility, and current code is instantaneous truth.
- Constrain interface structure, not model reasoning.

## 2) Update signal shape (ratified direction)

- Keep two dynamic values in `[0,1]`: `truth` and `utility`.
- At reflection time, the agent should provide adjustment direction/magnitude, confidence, rationale, and references.
- Do not use pure intuitive overwrite; apply bounded deterministic adjustments with damping.
- Exact parameter values remain open.

## 3) Evidence strictness split (with attribution reality)

- `truth` updates require evidence references.
- `utility` evidence is optional because attribution to a specific shellbrain is often hard in practice.
- When utility evidence is missing, update impact should be weaker or deferred until reinforced.
- Exact fallback behavior remains open.

## 4) Interface clarifications ratified late in the thread

- Use `read`, `write`, and `update`.
- Prefer one `update` operation with `mode: "dry_run" | "commit"` instead of separate `propose_update` and `apply_update` endpoints.
- `write` payloads must carry explicit `scope` and `kind`; no `auto` categorization in payloads.
- `read.kinds` is an include filter.
- A validation layer sits directly under the interface (schema validation + semantic validation).

## Open details

- Exact bounded update-function math (caps, damping, skip thresholds).
- Final no-evidence utility fallback policy (small delta vs defer).
