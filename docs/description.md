# this is what could be typed out.

you are building a brain for storing and recalling long-term memories.

it should be maximally useful for solving future problems you encounter.

it should support continual learning by aquiring new knowledge over time.

it should be flexible enough to store memories of any type.

it should be structured enough to resist entropy over years of accumulating knowledge.

it should learn from interacting with its environment.

it should ground all memories with evidence from interacting with its environment.

it should update its beliefs about the world when evidence changes.

it should be creative.



i am building a brain. first, we want a record of interaction with the environment. we need episodic memory.

next, we'll need a way to store facts about the world that we observe. we need semantic memory.

we want it to be maximally useful, so we want to store problems we encounter and their solutions.

we also want to store unsucessful solution attempts. we can learn a lot from those.

when facts about the world change we'll need to update those facts. we also probably want to remember the change
that prompted updating the fact. so we'll store the old fact, the change, and the updated fact.

it's possible for memories to relate to each other. we should capture these relationships.

it's pssible for memories to be similar to one another. we should capture these similarites.

similar memories will have their own set of similar memories. we should construct these similarity networks.

memories will be recalled when a problem is encountered.

recalled memories will have varying utility toward a problem's solution.

we should record these utilities.

let's build a brain.



# shellbrain - what a readme could look like.
shellbrain is a knowledge engine for AI agents.

shellbrain uses case-based reasoning to construct long-term knowledge that massively compounds your productivity.

shellbrain, in conjuction with teams of agents, implements a distributed continually learning cognitive system
that both aquires and makes use of knowledge that is uniquely yours.

# a memory ontology.

procedural memory.
shellbrain remembers every problem you have ever worked on.
shellbrain remembers every failed solution attempt to every problem so it can learn from what did not work.
shellbrain remembers every working solution to every problem you've ever worked on.
in aggregate, this memory set consitutes a "scenario". shellbrain remembers all of your scenarios.

semantic memory.
shellbrain remembers facts about the world, you, and your code.
shellbrain remembers changes to facts when facts about the world change.
shellbrain links stale facts to updated facts via change memories.

associative memory.
shellbrain has two types of associations: explict associations and implicit associations.
shellbarin forms explicit associations which are formal relationships between memories in a knowledge graph.
shellbrain forms implicit associations using semantic similarity via vector embeddings.
shellbrain implements creative recall by returning multiple memories linked by parameterizable "associative hops" (i.e., samantic activation networks)

episodic memory.
shellbarin remembers every experience you and your agent have had together.
shellbrain remembers all dialog between you and your agents.
shellbrain remembers your agents' tool use.

# a principled, reproducable epistomology.

shellbrain strictly prioritized observed reality as ground truth.
shellbrain grounds every memory with explicit evidence from episodic work sessions.

# memories have utility

shellbrain assigns utility to problem-specific utility to recalled memories.
shellbrain derives global utility to all memories.
