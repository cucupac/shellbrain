# Breakthrough Structured

*Goal:* Turn the raw note into a clear journey from "I hit a problem" to "shellbrain gets better over time".

*Reading rule:* **Settled** items come from existing `insights/` docs, and **Open** items are proposals we still need to decide.

## Journey 1: Problem Encounter

**Q:** What does the agent do with long-term shellbrain at the interface layer?  
**A:** The interface supports `query/read`, `write`, and `dispute` so the agent can retrieve, persist, and challenge memory.

**Q:** Why consult shellbrain when a new problem appears?  
**A:** Memory helps both solve by analogy (*case-based reasoning*) and narrow the solution search space.

**Q:** What rule applies when shellbrain conflicts with the codebase?  
**A:** **Settled:** *Current code is ground truth* and shellbrain is advisory because shellbrain can drift.

## Journey 2: Retrieval Plan

**Q:** How is the retrieval query structured?  
**A:** It has two lanes: **[A]** semantic retrieval with association expansion and **[B]** bounded keyword retrieval.

**Q:** What does lane **[A]** do first?  
**A:** Lane **[A]** finds vector-similar seed memories above a threshold.

**Q:** What happens after a seed is found in lane **[A]**?  
**A:** Lane **[A]** performs a two-hop association walk from each seed with decay so farther hops still clear relevance floors.

**Q:** What is the concrete expansion example from the raw note?  
**A:** If three seeds pass first-stage thresholding, the two-hop walk can grow to as many as nine memories if downstream thresholds are met.

**Q:** Why include lane **[B]** if lane **[A]** already uses embeddings?  
**A:** Lane **[B]** catches lexical blind spots semantic search may miss.

**Q:** How are results prepared for the LLM?  
**A:** A/B results are merged and deduplicated so context is non-redundant and token-efficient.

**Q:** How does this fit the existing architecture?  
**A:** **Settled:** It aligns with *scope -> relevance -> association -> threshold -> selection*.

## Journey 3: Storage Foundation

**Q:** What minimum data is required for this retrieval system?  
**A:** The database must store shellbrain text and an embedding vector linked to each shellbrain item.

**Q:** What core system pieces exist at this abstraction level?  
**A:** The system has an interface (`query/write/dispute`), a recall engine, and a database substrate.

**Q:** What storage model is already agreed?  
**A:** **Settled:** Use SQLite with one DB per repo plus one global DB.

**Q:** What persistence rule is already agreed?  
**A:** **Settled:** The event log is authoritative and cards/embeddings/indexes are rebuildable projections.

**Q:** How strong is repo isolation in the current design?  
**A:** **Settled:** Repo boundaries are physical so cross-repo facts do not leak.

## Journey 4: Memory Shape and Scope

**Q:** What shellbrain kinds are explicitly named in the raw note?  
**A:** The note names procedural memory, user preference memory, fact-based memory, and episodic immutable repo history.

**Q:** How does this compare to current ontology docs?  
**A:** **Open:** Current docs use experiential/preferences/structural (and also preference/fact/tactic language), so naming needs normalization.

**Q:** What should live in global shellbrain in this draft?  
**A:** Abstract user context such as current work focus, coding preferences, and goals is proposed for global scope.

**Q:** What hierarchy assumption appears in the raw note?  
**A:** The note assumes shellbrain is hierarchical, with abstract preference context above repo-specific operational detail.

**Q:** Is extra partitioning for higher-level memories already decided?  
**A:** **Open:** Separate table or separate DB for higher-level shellbrain is still undecided.

## Journey 5: Writing and Consolidation

**Q:** When does the agent draft a new shellbrain entry?  
**A:** The draft is produced after solving a problem through iterative user-agent work.

**Q:** How does the agent stay adaptive if the conversation changes direction mid-session?  
**A:** The agent can re-read long-term shellbrain at any time to reload relevant context before continuing.

**Q:** What is the default human-control behavior before writing?  
**A:** Proposed default behavior is explicit user confirmation of what will be saved and where it will be categorized.

**Q:** What is the low-friction mode for users who do not want manual confirmation each time?  
**A:** **Open:** Add a configurable auto-store mode so the agent can write autonomously.

**Q:** What pre-write checks are proposed for auto-store?  
**A:** Re-run original retrieval, test new-shellbrain similarity for duplicates, store if novel, reinforce if redundant, and resolve contradictions.

**Q:** How is redundancy handled?  
**A:** Redundant Shellbrain entries should strengthen an existing entry rather than create a duplicate, with redundancy judged by the LLM.

**Q:** How are contradictions grounded for code-facts?  
**A:** If a shellbrain contradicts current code facts, the conflicting shellbrain should be weakened because code has priority.

## Journey 6: Scoring and Feedback

**Q:** What new mechanism appears once we discuss weakening or strengthening memories?  
**A:** The design introduces a shellbrain-strength signal.

**Q:** Should strength be part of ranking math or only exposed to the LLM for judgment?  
**A:** **Open:** This is undecided between hard ranking (`similarity + strength`) and advisory metadata.

**Q:** What concern is raised about explicit truth scoring?  
**A:** **Open:** Truth scoring may be too mechanistic for a low-volume interaction engine.

**Q:** What alternative axis is proposed instead of truth?  
**A:** Helpfulness is proposed as the primary signal via upvotes/downvotes.

**Q:** How does filtering work in the helpfulness model?  
**A:** Memories stay retrievable until enough downvotes accumulate, after which they are filtered out.

**Q:** When is helpfulness feedback applied?  
**A:** At the end of each work session, the agent can rate which retrieved memories were helpful.

## Journey 7: The Breakthrough (Now Extended)

**Q:** What core distinction triggered the original breakthrough?  
**A:** Memory should explicitly separate *problems* from *solutions* while linking them.

**Q:** What new distinction was added after that?  
**A:** Failed attempts should be stored as a first-class shellbrain type separate from solutions but still linked to problems.

**Q:** Why not keep failed attempts only in the immutable episodic log?  
**A:** The episodic log is evidence, but retrieval needs normalized memories of what worked and what failed.

**Q:** What structure does this imply at storage level?  
**A:** The model now implies linked `problems`, `solutions`, and `failed_tactics` records.

**Q:** What set is searched during retrieval under this extended model?  
**A:** Vector and keyword retrieval run over the union of problem, solution, and failed-tactic memories.

**Q:** What happens when either side is matched during retrieval?  
**A:** Matching any node can pull its linked problem context plus successful and failed attempts.

**Q:** How is final context assembled before delivery?  
**A:** Pull from **[A]** and **[B]**, expand across links, then merge to a unique set.

**Q:** How should failed attempts be presented to the agent?  
**A:** Failed tactics should be shown as avoid-or-reconsider signals rather than candidate solutions.

**Q:** Why is this extension a major design gain?  
**A:** It preserves validated solution shellbrain while adding anti-pattern shellbrain that reduces repeated dead ends.

## Journey 8: Session-End Capture From Notes

**Q:** What role does the immutable episodic log play in this extension?  
**A:** It serves as the agent's raw notebook for reconstructing what was tried during the session.

**Q:** What should happen at session end before writes are finalized?  
**A:** The agent should review notes plus working context, then extract and classify attempts as worked or failed.

**Q:** Where are classified attempts written?  
**A:** Worked attempts become linked solutions and failed attempts become linked failed-tactic memories.

## Next Open Decisions

**Q:** What should we decide first to move from ideation to implementation?  
**A:** Decide feedback semantics, ranking coupling, failure taxonomy granularity, ontology naming normalization, and higher-level partition boundaries.
