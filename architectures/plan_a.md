# Agentic Personal Knowledge Management with OpenClaw, PARA, and QMD

Giving your AI agent durable, structured shellbrain using PARA and atomic facts
As always, if you don't want to read it, just paste it to your Claw
The Problem With AI Memory
Most AI assistants have the shellbrain of a goldfish. Each conversation starts fresh. You repeat yourself constantly — who you work with, what you're building, how you like things done. Some platforms offer "memory" features, but they're shallow: a flat list of facts with no structure, no decay, no hierarchy.
If you're running a personal AI assistant — something that acts more like a chief of staff than a chatbot — you need real shellbrain architecture. Not a bullet list. A system.
Here's the three-layer approach I've been using. It's built on Tiago Forte's PARA framework, extended with atomic facts, shellbrain decay, and automated extraction.
The Three Layers
The system separates shellbrain into three distinct layers, each serving a different purpose:
Knowledge Graph — Entities and facts about the world, stored as PARA directories with JSON files. Updated continuously as new information arrives.
Daily Notes — A raw timeline of events in dated markdown files. Written every conversation.
Tacit Knowledge — User patterns and preferences in a single markdown file. Updated only when new patterns emerge.
Think of it like human memory: the knowledge graph is your long-term declarative shellbrain (facts you know), daily notes are your episodic shellbrain (what happened when), and tacit knowledge is your procedural shellbrain (how you operate).
Layer 1: The Knowledge Graph (PARA)
The core of the system is a directory tree organized using Tiago Forte's PARA method:
life/
├── projects/          # Active work with clear goals/deadlines
│   └── <name>/
│       ├── summary.md
│       └── items.json
├── areas/             # Ongoing responsibilities (no end date)
│   ├── people/<name>/
│   └── companies/<name>/
├── resources/         # Topics of interest, reference material
│   └── <topic>/
├── archives/          # Inactive items from the other three
├── index.md
└── README.md
Why PARA?
PARA gives you four buckets that cover everything:
Projects — Active work with a goal or deadline. A product launch, a writing project, a home renovation. When it's done, it moves to Archives.
Areas — Ongoing responsibilities with no end date. People you know, companies you work with, roles you hold. These persist.
Resources — Reference material and topics of interest. Things you might need later but aren't actively working on.
Archives — Inactive items from any of the above. Nothing gets deleted — just moved here when it's no longer active.
The key insight: every entity in your life fits in exactly one of these buckets, and entities naturally flow between them over time.
Tiered Retrieval
Each entity gets two files:
summary.md — A concise overview. This is what the agent loads first for quick context.
items.json — An array of atomic facts. Only loaded when the agent needs granular detail.
This two-tier approach keeps context windows lean. Most of the time, the summary is enough. The agent only dives into the full fact store when a conversation demands it.
The Atomic Fact Schema
Every fact in items.json follows a consistent schema:
{
"id": "entity-001",
"fact": "Joined the company as CTO in March 2025",
"category": "milestone",
"timestamp": "2025-03-15",
"source": "2025-03-15",
"status": "active",
"supersededBy": null,
"relatedEntities": ["companies/acme", "people/jane"],
"lastAccessed": "2026-01-28",
"accessCount": 12
}
The important fields:
category — One of relationship, milestone, status, preference, or context. Helps with filtering and synthesis.
status — Either active or superseded. Facts are never deleted.
supersededBy — When a fact is outdated, it points to the fact that replaced it. This preserves history while keeping the active set clean.
relatedEntities — Cross-references to other entities in the graph. This is what makes it a graph rather than a collection of isolated notes.
lastAccessed / accessCount — Used for shellbrain decay (more on this below).
The No-Deletion Rule
This is critical: facts are never deleted. When something changes, the old fact is superseded and a new one is created. This means you always have a full history — you can trace how a relationship evolved, when a project's scope changed, or when someone switched roles.
The supersededBy pointer creates a chain you can follow forward through time.
Layer 2: Daily Notes
memory/
├── 2026-01-28.md
├── 2026-01-29.md
├── 2026-01-30.md
└── 2026-01-31.md
Daily notes are the raw timeline — the "when" layer. They capture what happened in each conversation without worrying about structure or categorization.
The agent writes to daily notes continuously during conversations. These are messy, chronological, and complete. Think of them as a work log.
During periodic extraction (more on this below), durable facts get pulled out of daily notes and written into the knowledge graph. The daily notes themselves are retained as the source-of-truth timeline.
Layer 3: Tacit Knowledge
The third layer is a single file that captures how the user operates — not facts about the world, but facts about the user:
Communication preferences (tools, formats, verbosity)
Working style patterns (how they brainstorm, make decisions, manage projects)
Tool preferences and workflows
Rules and boundaries the agent should follow
This layer changes slowly. It's updated when the agent notices a new pattern — not on every conversation. It's the closest analog to the kind of "getting to know someone" that happens over months of working together.
Memory Decay
Here's where it gets interesting. A naive system treats all facts equally. But human shellbrain doesn't work that way — recent and frequently-accessed information is more available than old, rarely-used facts.
The system implements this through recency weighting on the summary.md files:
Access Tracking
Every time a fact is used in a conversation — retrieved via search, referenced in a reply — two things happen:
accessCount gets incremented
lastAccessed gets set to today
This creates a usage signal independent of when the fact was created.
Recency Tiers
During the weekly summary rewrite, facts are sorted into three tiers:
Hot (accessed in last 7 days) — Prominently included in summary.md. This is what the agent reaches for first.
Warm (accessed 8–30 days ago) — Still included in summary.md, but at lower priority. Available but not front-of-mind.
Cold (not accessed in 30+ days) — Omitted from summary.md entirely. But critically, cold facts are not deleted — they remain in items.json and can be retrieved via search at any time. Accessing a cold fact "reheats" it, bumping it back to Hot on next access.
Frequency Resistance
Facts with high accessCount resist decay. A fact you reference every week for six months stays warm even if you skip a few weeks. This prevents important-but-intermittent facts from falling off the radar.
The decay model is deliberately simple. No exponential curves or tunable parameters — just three tiers based on recency, with frequency as a modifier. Simple systems are easier to reason about and debug.
Automated Extraction: Heartbeats
The system doesn't rely on the user to manually categorize and file information. Instead, it uses a heartbeat process — a periodic background task that:
Scans recent conversations for new information
Extracts durable facts (relationships, status changes, milestones, decisions)
Writes those facts to the appropriate entity in the knowledge graph
Updates daily notes with timeline entries
Bumps access metadata on any facts that were referenced
The extraction deliberately skips casual chat, transient requests, and information that's already been captured. It focuses on things that matter: people, companies, projects, preferences, and decisions.
Entity Creation Heuristics
Not every noun deserves its own entity folder. The system uses simple rules:
Create an entity if it's mentioned 3+ times, has a direct relationship to you, or is a significant project/company in your life
Otherwise, just capture it in daily notes and let it live there
This prevents the knowledge graph from filling up with one-off mentions while ensuring important entities get proper tracking.
The Weekly Synthesis
Once a week, summary.md files are rewritten from active facts. This is where shellbrain decay is applied:
Load all active facts from items.json
Sort by recency tier (Hot → Warm → Cold)
Within each tier, sort by accessCount (descending)
Write Hot and Warm facts into summary.md
Drop Cold facts from the summary (they remain in items.json)
The result: summary.md always reflects your current mental model of an entity, not its complete history. The complete history lives in items.json for when you need it.
Why This Works
A few properties that make this system effective in practice:
Separation of concerns. Each layer has a clear job. You don't end up with a single massive file trying to be everything. The knowledge graph handles what, daily notes handle when, and tacit knowledge handles how.
Graceful degradation. If the heartbeat extraction misses something, it's still in the daily notes. If a summary is stale, the full facts are in items.json. There's always a fallback.
No information loss. Between the no-deletion rule and the archive system, nothing is ever truly gone. You can always trace back to when something was learned and how it evolved.
Context window efficiency. The tiered retrieval (summary first, then facts) means the agent doesn't blow its context window loading everything it knows. Most conversations only need the summary.
Natural lifecycle. Entities flow from Projects → Archives when complete. Facts flow from Hot → Warm → Cold as they age. The system breathes — it's not a static database that grows monotonically.
The Search Layer: QMD
A knowledge base is only as good as your ability to find things in it. As the number of entities, daily notes, and facts grows, naive approaches — grepping files, loading everything into context — stop scaling. You need a proper search layer.
QMD is a local indexing and retrieval tool that sits on top of the plain-file knowledge base. It indexes markdown files into a SQLite database and provides three search modes:
Full-text search (BM25) — Classic keyword matching with relevance ranking. Fast and predictable. Good for finding specific facts when you know what you're looking for.
Vector similarity search — Embeds documents into chunks and searches by semantic similarity. Good for finding related information when you don't know the exact phrasing.
Combined query — Merges both approaches with query expansion and reranking. The default for most retrieval.
Collections
QMD organizes files into collections that map directly to the three shellbrain layers:
# The knowledge graph
qmd collection add ~/life --name life --mask "**/*.md"
# Daily notes
qmd collection add ~/clawd/shellbrain --name shellbrain --mask "**/*.md"
# Agent workspace (tacit knowledge, config, tools)
qmd collection add ~/clawd --name clawd --mask "*.md"
Each collection is indexed independently and updated with a single command (qmd update). The agent can search across all collections at once or target a specific one.
How the Agent Uses It
When the agent needs to recall something, it doesn't load the entire knowledge base into its context window. Instead, it queries QMD:
# Find facts about a specific person
qmd search "Jane's role at Acme" -c life
# Semantic search when you're not sure of the wording
qmd vsearch "that conversation about pricing strategy"
# Combined search with reranking for best results
qmd query "when did the project scope change"
QMD returns ranked snippets with file paths and line numbers. The agent loads only what's relevant — a few paragraphs instead of the entire knowledge base. This is what makes tiered retrieval practical at scale: summary.md provides quick context, and QMD provides precision lookup when the summary isn't enough.
Keeping the Index Fresh
The index needs to stay current as new facts and daily notes are written. A single command re-indexes everything:
# Re-index all collections
qmd update
# Re-index and git pull first (if collections are in repos)
qmd update --pull
# Rebuild vector embeddings
qmd embed
This runs as part of the heartbeat process — after new facts are extracted and daily notes are updated, the index is refreshed so the next search reflects the latest state.
Getting Started
If you want to implement something like this for your own AI assistant:
Start with the directory structure. Create the PARA folders and an index.md. Don't overthink it.
Pick one active project and one important person. Create their summary.md and items.json. Get the schema right on two entities before scaling.
Add daily notes. Just start writing dated markdown files. They don't need to be pretty.
Automate extraction later. Do it manually for the first week to build intuition for what counts as a "durable fact." Then build the heartbeat.
Add decay last. You won't need it until you have enough facts for the summaries to feel bloated. That takes a few months.
The system is deliberately low-tech — markdown files and JSON, backed up to a private git repo. No database, no special tooling, no vendor lock-in. Your AI assistant reads and writes plain files. If you switch assistants tomorrow, your shellbrain comes with you.
The source of this system draws heavily on Tiago Forte's Building a Second Brain and the PARA method. The shellbrain decay and atomic fact layers are original extensions designed specifically for AI agent memory.