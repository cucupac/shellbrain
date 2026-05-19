---
name: clean-architecture
description: "Define and enforce the owner's language-agnostic clean-core architecture for new software projects and refactors. Use when deciding responsibility placement, dependency direction, structural stage, safe refactor moves, semantic types, pure policies, entrypoints, startup wiring, adapters, and dependency boundaries."
---

# Clean Architecture

## Overview

Use this skill to decide three things during architecture work:

1. Where each responsibility belongs.
2. Which dependencies are allowed.
3. How much structure is justified at the current size.

Prefer a clean core: domain rules and use-case orchestration stay separable from real-world effects; effects enter through explicit boundaries; important domain values use semantic types when invalid primitives would cause misuse; and abstractions exist only when they protect testing, substitution, or boundary clarity.

Do not add abstractions for speculative future shape. Minimal abstractions are preferred unless an interface, type, boundary, or package protects testing, substitution, dependency direction, or reader clarity today.

The four-zone vocabulary is a practical carving, not a natural law: it separates domain meaning, concrete effects, inbound surfaces, and composition. If a repo uses different names, preserve those roles and dependency direction rather than forcing these labels.

Treat names as flexible when a repo has established vocabulary, but keep these boundary semantics stable:

- `entrypoints` are inbound ways the outside world calls the program: CLI, HTTP, jobs, hooks, commands, routes, handlers, presenters, argument parsing, and wire-format parsing when needed. Inbound surfaces and transport-specific request/response code live here.
- `startup` is the composition root: build concrete dependencies, select implementations, and wire adapters into core workflows.
- `core` is what the system means and does: entities, use cases, interfaces, policies, deterministic transformations, and shared domain errors.
- `adapters` is what the program talks to or controls, grouped by external system or mechanism: DBs, filesystems, clients, host apps, subprocesses, telemetry stores, reporting output, embeddings, and local state. Outbound implementations live here.

If `architecture-test.md` is available, use it for expanded smell lists, refactor sequences, and prompt templates; this skill must still contain the minimum placement and boundary tests needed to proceed without it.

## Invariant vs. Expression

This skill has two layers. Confusing them is the most common failure mode.

**The invariant** must hold at every size:

- Dependencies point inward toward domain logic.
- Pure rules are separable from effects.
- Concrete effect mechanisms do not enter core; when core must orchestrate an effect, it depends on parameters, callbacks, or domain-owned interfaces chosen at the lightest useful expression.
- Invariants live with the type that has them.

**The expression** scales with service size:

- Whether zones are files, modules, directories, or separate crates/packages.
- Whether folder names are literal (`core/`, `adapters/`) or implicit.
- How deeply nested the structure is.

The invariant is non-negotiable. The expression is chosen to make the invariant visible at the current scale. Pick the lightest expression that makes the invariant legible. Promote up when legibility breaks.

## Escalation Ladder

The four zones describe roles, not mandatory folders. How they are expressed depends on the service.

### Stage 1 - Single-module service

- **Fits:** scripts, small CLIs, single-responsibility binaries, pure algorithm libraries; typically under ~500 LOC.
- **Expression:** one or two files. Pure logic and effects separated within the file or across two files. Traits/interfaces defined alongside the domain types that own them.
- **Do not create:** dedicated zone folders, separate startup module, interfaces directory.

### Stage 2 - Flat module layout

- **Fits:** small services with a single responsibility; roughly 500-2,000 LOC; few effects.
- **Expression:** flat `src/` with named modules, such as `domain`, `adapters`, and `main`. Domain types and interfaces in one module, adapter implementations in another, wiring in `main` or equivalent.
- **Do not create:** subdirectories per zone.

### Stage 3 - Zone subdirectories

- **Fits:** services with multiple responsibilities, several adapters, or growing past the point where a flat module list is legible. Often this appears beyond ~2,000 LOC, but promote earlier only when responsibilities or adapters make the flat shape ambiguous.
- **Expression:** create explicit zone subdirectories only for roles with real substance. A common shape is `src/core/`, `src/adapters/`, and `src/entrypoints/`, with `main` or equivalent as startup, but keep a role as a file or flat module when a directory would be empty, near-empty, or less informative than the file name.

### Stage 4 - Workspace crates / packages

- **Fits:** multiple binaries sharing a domain, or any service where compiler-enforced dependency direction is worth the overhead.
- **Expression:** `core` is its own crate/package and literally cannot import adapters. Direction is enforced at the build-graph level.

### Promotion triggers

Promote up one stage when the current stage stops making the invariant legible, not on a calendar or LOC count alone.

Concrete triggers:

- A reader cannot tell where to look for a piece of logic in under ~10 seconds.
- A module's internal boundaries have become unclear.
- More than one binary needs to share domain code.
- Boundary violations have started appearing because the structure does not make the right placement obvious.

LOC ranges are sanity checks, not promotion rules. Role count, effect count, number of binaries, and boundary legibility outrank size.

Operational legibility test: given one new responsibility, an agent should be able to name its role and destination without opening more than three files and without choosing between two equally plausible homes. Legibility has broken when peer modules mix unrelated reasons to change, the same kind of rule appears in multiple zones, a responsibility requires hunting through unrelated files, or a corrected boundary violation reappears because the current shape does not make the allowed placement obvious.

Never promote speculatively. The lightest expression that works is the right one.

## Form Matches Content

Do not create empty or near-empty zones. A folder with one file or no files signals that the form is lying about the content; a reader sees `adapters/` and expects substance.

Specifically:

- No empty `core/interfaces/` directory if there are no interfaces.
- No empty `adapters/` directory if there is no adapter code.
- No speculative `entrypoints/http/` if the service only exposes a CLI.
- No `core/errors.*` file holding a single error that could live with its use case.

If a stage of the ladder forces a near-empty zone, you are at the wrong stage. Drop down.

This is not aesthetic preference. Empty zones increase navigation cost, mislead pattern-matching agents, and erode trust in the structure. Elegance here is correctness.

## Core Categories

Use these categories only when a repo is at Stage 3+ or otherwise has a real core package/directory. They are buckets for substantial core content, not mandatory folders.

- `core/entities`: domain state types and semantic value objects. Enforce invariants at construction and state-transition boundaries when invalid values should not travel through the system.
- `core/use_cases`: workflows plus their local `request.*`, `result.*`, and use-case-specific `errors.*`. Requests and results are not persistence models, wire payloads, or schemas. Use cases orchestrate work without owning every rule.
- `core/interfaces`: outbound behavior interfaces the core needs from outside, such as repositories, clocks, ID generators, query adapters, external clients, and units of work. Create these only when they protect testing, substitution, or dependency direction today.
- `core/policies`: pure rules, decisions, calculations, and cross-aggregate invariants over already-loaded values.
- `core/errors.*`: shared expected errors only. Keep errors used by one workflow beside that use case.

Do not create these buckets by default:

- `core/contracts`: put request, result, and local error types beside the use case that owns them.
- `core/schemas`: reserve schema/protocol language for entrypoint wire validation or DB schema.
- `core/effects`: put concrete output fields in the owning result type unless a specific domain category emerges.
- alternate outbound-interface buckets: use `core/interfaces` for outbound behavior supplied by adapters.
- top-level `handlers` or `application`: handlers are inbound and belong under the relevant entrypoint surface; use concrete use cases and startup wiring instead of a vague application layer.
- default entrypoint `protocol` folders: use specific names such as `args.*`, `routes/`, `commands/`, `handlers/`, `presenters/`, `request_parsing/`, `json_payloads/`, or `error_responses/` when those concepts really exist.

## Review Mode

For architecture audits, inspect before judging. Cite `file:line`, rank findings by severity, explain the violated boundary, and give concrete moves, renames, splits, or guardrail tests. Do not call code "clean" or "messy" without evidence. If the user asks for audit-only, do not mutate code.

Bounded audit mode: an architecture audit is not an exhaustive architecture encyclopedia. Make one pass that identifies the current stage, runtime surfaces, core domain rules/invariants, real-world effect edges, dependency-direction violations, and the top structural mismatches. Report the smallest set of findings that changes the next engineering move, usually 3-7 items. Do not enumerate every possible test, async, auth, telemetry, CI, versioning, or cross-cutting concern unless the repo actually shows that concern or the user asks. Stop when the highest-leverage boundary violations are named, the next safe refactor is clear, and remaining issues are speculative.

For Stage 3 or Stage 4 repos, recommend lightweight boundary checks when the language or build system supports them: core must not import adapters, startup, or entrypoints; adapters must not import startup or entrypoints; entrypoint handlers must not import concrete adapters or call startup wiring. Put these checks in existing test/CI infrastructure when available. Do not introduce a new build system solely to enforce architecture unless the user asks or boundary regressions are already recurring.

## Placement Preamble

For architecture work, briefly say where each responsibility belongs and why before proposing or editing. Example: CLI command parsing goes in `entrypoints/cli`; the audit workflow goes in `core/use_cases/audit_pool`; repository behavior is a `core/interfaces` trait; the Postgres implementation goes in `adapters/postgres`.

## Configuration And Settings Placement

Do not treat configuration as adapter code by default.

Split config responsibilities like this:

- Packaged default config files, such as YAML/TOML shipped with the app, may live in an app-owned package-data folder such as `app/settings/`. Treat this as configuration data, not a runtime layer.
- Startup owns loading, selecting, merging, and coercing config for composition. Good fits: `startup/config.*`, `startup/settings.*`, or framework-native settings modules.
- Core owns typed settings/value objects only when settings have domain meaning or invariants. Good fit: `core/entities/settings.*`.
- Core should receive typed settings through use-case requests or explicit parameters. Do not add a `core/interfaces/settings` provider unless a core use case truly needs substitutable config-reading behavior.
- Adapters own config only when the program talks to an external config mechanism, such as Vault, AWS SSM, Consul, Kubernetes secrets, a mutable local state store, or a remote config service. Name that folder after the mechanism, not `settings_files`.

Avoid recommendations like `adapters/settings_files`, `adapters/config`, or config-provider interfaces when the code is only loading app-packaged defaults during startup.

## Public Boundary

Libraries, crates, packages, and services should expose only intentional public API. Keep internal layers private where the language supports it. Public request/result types should protect request-shape consistency when needed. Public entities and semantic values should protect domain invariants with private fields, constructors, and accessors when invalid combinations matter.

Version public wire APIs at the entrypoint boundary. Keep core request/result and entity types version-neutral unless the domain meaning itself changed. Put v1/v2 route names, payload schemas, compatibility mappers, and deprecation envelopes in entrypoints. Use adapters only for versioned external systems the program calls. Do not add version suffixes to core types for transport-only compatibility.

## Special Cases

**Replicated implementations.** For replicated model families or parallel implementations where each variant must stay independent for auditability, parity, or isolation, duplicated code is intentional. Do not DRY across replicas with shared helpers; independence is the feature.

## Workflow

### 1. Inventory the runtime surface

Inspect the repo before proposing structure changes.

- Find the real entrypoints, stateful integrations, persistence edges, transport layers, and external dependencies.
- Identify the main domain concepts, canonical data shapes, business rules, state transitions, invariants, and expected failure modes.
- Identify which values are meaningful primitives that deserve semantic types, such as IDs, addresses, dates, counts, distances, money, rates, buckets, queries, or statuses.
- Separate the target architecture from current shortcuts or layering leaks.
- Write a vocabulary map before renaming: for each established repo term, record which role it plays here: core, adapter, entrypoint, startup, or mixed. Do not rename solely to match this skill's vocabulary; rename only when the current term hides a boundary violation, creates two plausible homes for the same responsibility, or conflicts with peer names.

### 2. Define the boundary model

State the intended dependency direction explicitly.

- `core -> core`
- `adapters -> core`
- `startup -> core + adapters`
- `entrypoints -> core`
- `outermost entrypoint bootstrap/main path -> startup`

Violations and limits:

- `core -> adapters`, `startup`, or `entrypoints` is a violation unless kept as a small, temporary compatibility seam with a clear removal path.
- `adapters -> startup` or `entrypoints` is a violation.
- Entrypoint handlers, routes, commands, job functions, presenters, and parser code should not call startup; they receive already-composed use cases or callable dependencies.
- Only the outermost entrypoint bootstrap/main path should invoke startup wiring, and it should do so to obtain composed dependencies.
- Startup composes dependencies; it should not become a service locator that handlers call during request/job execution.

### 3. Place responsibilities deliberately

Run the architecture test on each responsibility:

- If the logic expresses domain meaning or can run against mocked interfaces and still make sense, place it in `core`.
- If the logic receives outside input, validates wire shape, maps transport payloads to use-case requests, invokes an already-wired use case, or renders output, place it in `entrypoints`.
- If the logic talks to or controls a DB, network, filesystem, process, host app, package manager, browser, telemetry store, external service, or vendor payload, place it in `adapters`.
- If the logic only assembles concrete dependencies, place it in `startup`.

Use this split when deciding where code belongs:

- Rule code: pure calculations, validation, decisions, transformations, state transitions, and cross-aggregate rules.
- Real-world code: database calls, network calls, filesystem access, framework objects, logging emission, retries, transactions, subprocesses, clocks, random generators, and host integrations.

Rule code belongs in `core`. Real-world code belongs in `adapters`, `startup`, or `entrypoints`. Use cases may orchestrate real-world effects through parameters, callbacks, or interfaces, but should not hide concrete IO inside domain rules.

Place tests by the boundary they exercise. Core tests cover pure rules, entities, policies, and use cases with fakes or in-memory implementations, and should not import concrete adapters. Adapter tests cover concrete DB, filesystem, network, subprocess, telemetry, or vendor behavior. Entrypoint tests cover parsing, transport validation, request mapping, response rendering, and error envelopes. Startup tests should be thin smoke tests for composition. Add architecture/import tests only when the repo has enough structure for dependency direction to regress.

When present, place cross-cutting concerns by what they mean, not by the fact that they cut across files. Logging and telemetry clients live in entrypoints, adapters, or startup; core may return domain events, result metadata, or structured facts for the edge to emit. Retries, timeouts, circuit breakers, and backoff live around concrete IO in adapters or startup wiring. Transaction boundaries belong in use-case orchestration through a core-owned unit-of-work interface only when business consistency matters; concrete transaction APIs live in adapters. Authentication parsing and credential verification live at the edge; authorization rules with domain meaning live in core policies or use cases. Feature-flag loading lives at the edge; feature decisions with domain meaning enter core as typed inputs or policies.

For async and event-driven flows: message consumers, scheduled jobs, webhook handlers, and queue-triggered functions are entrypoints. Broker clients, queue implementations, webhook delivery clients, and event-store integrations are adapters. Wire event schemas and vendor payloads are parsed at entrypoints or adapters and mapped into core request/result/domain types. Domain events are core facts only when they express something that happened in the domain; publishing, serialization, retries, dead-letter handling, acknowledgements, and delivery guarantees stay at the edge.

### 4. Place validation, state, errors, and evidence intentionally

- Domain invariants go in semantic types, entities, constructors, or state-transition functions.
- Request-shape validation can live in use-case request types.
- Cross-aggregate pure rules that need multiple already-loaded entities go in `core/policies`.
- Repo-backed checks belong in use cases, or in policies that receive explicit already-loaded values and leave loading to the use case.
- Wire-format validation belongs in entrypoint parsing or handler code; do not force CLI/HTTP payload shape checks into domain types.

Use this error taxonomy: domain-expected outcomes live in core as typed result states or expected errors, shared only when multiple workflows use them and local beside the owning use case otherwise. Request-shape and wire-format errors live in entrypoints and are translated into transport-specific envelopes there. Infrastructure errors from DBs, networks, filesystems, subprocesses, telemetry, or vendors live in adapters; use cases may translate them into domain-expected outcomes only when the business meaning is explicit. Retryable/transient handling belongs in adapters or startup policy unless retry state has domain meaning. Do not leak adapter exception types into core or transport responses.

When auditability, provenance, or truth evolution matter: core owns the domain meaning of normalized records, lifecycle states, provenance concepts, and idempotency rules. Entrypoints or adapters capture raw request/response payloads and map them to core concepts. Adapters own storage schemas, append-only tables, external IDs, and persistence mechanics. Prefer explicit lifecycle transitions, deterministic IDs or natural idempotency keys, raw evidence records, and append-only provenance over silent mutation when those concepts affect business truth.

### 5. Check for boundary anti-patterns

After placing responsibilities, scan for these failure modes:

- domain rules hidden in clients, repositories, ORM models, handlers, commands, controllers, managers, or framework callbacks
- core modules importing framework objects, concrete IO, loggers, clocks, random generators, subprocesses, vendor payloads, or adapter exceptions
- important concepts traveling as loose strings, ints, dicts, or untyped errors when invalid values can cause misuse
- catch-all modules or folders such as `_shared`, `helpers`, `utils`, `operations`, `agent_operations`, `runtime`, or `application` that hide why files change together
- speculative entities, tables, interfaces, compatibility aliases, layers, or folders that no current use case needs
- shared helpers that deduplicate intentionally independent replicas
- inconsistent peer naming that creates two plausible homes for the same responsibility
- generic verbs such as `apply_*` when the domain operation is `add`, `update`, `delete`, `approve`, `reject`, `publish`, `capture`, or another specific action

Keep this scan bounded. Do not expand it into a huge smell catalog.

### 6. Apply the skill differently for greenfield and refactor work

For greenfield work:

- pick a stage on the ladder. Default to the lightest stage that fits the expected initial scope. Resist starting at Stage 3 unless you already know multiple zones will carry substance.
- define the main use-case boundary.
- identify inputs, outputs, invariants, expected errors, transaction boundaries, side effects, and reporting needs.
- set up entities, value objects, use cases, request/result types, interfaces, policies, shared errors, and adapter boundaries only where current use cases need them.
- keep the first vertical slice narrow, but make the invariant real from line one.
- pick directory names that fit the language and the chosen stage; preserve dependency direction regardless.

For refactors:

- preserve behavior first.
- identify the highest-leverage boundary leaks.
- move repeated validation and important invariants into semantic domain types where it reduces misuse.
- extract pure rules from orchestration before changing IO behavior.
- fix dependency direction before polishing naming.
- move request/result/local error types into the owning use case.
- restore `core/interfaces` when older outbound-interface bucket names exist.
- remove compatibility aliases when the user does not want backwards compatibility.
- collapse speculative abstractions after the behavior is protected.
- group adapters by the external thing controlled and the reason files change together.

**Invariant before expression.** A messy Stage 2 service with correct dependency direction is healthier than a clean Stage 3 service whose `core` imports adapters. Do not promote stages as part of a behavior-preserving refactor unless the current stage has become illegible. Fix direction first; restructure second.

Stop a refactor when the named boundary violation is removed, behavior is protected, and the remaining structure passes the operational legibility test. Do not continue into naming, folder, or abstraction changes unless they remove a current ambiguity or user-requested compatibility concern.

### 7. Produce useful output

If the user asks for guidance, return:

- a short placement map that says where each responsibility belongs and why
- the target architecture in plain language
- the current violations or risks
- the domain concepts that should become semantic types, and the invariants they should enforce
- the rule code that should be pure and the real-world code that should stay at the edge
- the concrete placement rules for the code in question
- a small refactor plan ordered by leverage and safety

If the user asks for implementation, make the changes directly while preserving the boundary model.

If the user asks for a prompt for another agent and `architecture-test.md` is available, use its templates; otherwise write the prompt from the placement map, boundary model, violations, semantic types, pure rules, real-world edges, and ordered refactor plan above.

## Recall Surface

Prefer: clean core, thin entrypoints, explicit startup, semantic types, pure policies, typed expected outcomes, explicit side-effect boundaries, minimal abstractions, and the lightest structure that keeps boundaries legible.

Avoid: vague layers, dumping-ground folders, fat handlers, framework bleed into core, hidden domain rules, primitive obsession, stringly errors, hidden globals, speculative abstractions, and inflated structure.
