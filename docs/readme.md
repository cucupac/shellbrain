# shellbrain

shellbrain is a knowledge engine for AI agents.

it gives agents long-term memory grounded in what actually happened. it retrieves that memory when the current problem resembles something already seen. over time, the agent compounds — solving faster, failing less, and recalling things it would never think to look for.

shellbrain is recall, not authority. the current repo is ground truth. memories help solve the problem in front of you. they do not overrule what the code says now.

---

## case-based reasoning.

shellbrain remembers every problem you have ever worked on.

shellbrain remembers every working solution to every problem.

shellbrain remembers every failed attempt — so it learns from what did not work.

solutions and failed tactics are linked to the problem they belong to. without that link, they are invalid. shellbrain enforces this.

each problem, its solutions, and its failed tactics form a scenario. shellbrain remembers all of your scenarios.

the next time a similar problem appears, shellbrain retrieves the relevant scenarios and gives the agent a head start.

---

## knowledge that evolves.

shellbrain remembers facts about the world, your repo, and your code.

shellbrain never overwrites facts. when a fact changes, shellbrain stores the change that invalidated it, stores the updated fact, and links all three: old fact → change → new fact.

beliefs are never silently mutated. history is always preserved.

shellbrain also remembers how you like to work — repo conventions, style decisions, what should win when there is ambiguity. these are durable memories, learned from working with you.

---

## grounded in evidence.

shellbrain records every interaction between you and your agent. all dialog. all tool use. every event from every work session.

this is episodic memory, and it is the foundation everything else is built on.

every durable memory must trace back to a real event. evidence is never invented. if the evidence is ambiguous, shellbrain skips the write entirely.

shellbrain would rather have no memory than a memory it cannot justify.

---

## creative recall.

memories relate to each other. shellbrain captures these relationships in two ways.

explicit associations are formal links in a knowledge graph — `depends_on` and `associated_with` — stored as first-class records.

implicit associations are computed from semantic similarity via vector embeddings.

when a problem triggers retrieval, shellbrain does not just return direct matches. it seeds candidates from semantic and keyword search, then expands outward — through linked scenarios, fact-update chains, association edges, and semantic neighbors. it scores, deduplicates, and returns a bounded context pack.

each result explains why it was included. the pack is capped. this is intentional — retrieval is precise, not exhaustive.

the interesting part: chaining through multiple associative hops surfaces memories the agent would not think to look for. recall starts to look like creativity.

---

## utility is per problem.

a memory can be critical for one class of problem and useless for another.

shellbrain does not assign a single global score. it records utility per problem — a vote in [-1.0, 1.0] for each memory against each problem it was recalled for.

global utility is derived from these observations, not assumed.

---

## four operations.

shellbrain exposes four agent-facing commands:

**read** — retrieve memories related to a concrete problem. does not mutate state.

**events** — inspect recent evidence from the active session. this is how the agent knows what just happened.

**create** — add one durable memory. at least one evidence reference is required.

**update** — record utility, evolve facts, add associations, or archive.

that is the entire surface area.

---