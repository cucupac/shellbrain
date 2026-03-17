okay. so all of that makes sense. i think what i need personally is a series of questions and answers. i will come up with some of the questions. but if there are other obvious ones, write them too.

i am thinking:
- one sentence question
- one setence answer

i'll start by writing some of these. again, i am trying to understand and create this from the outside in.

as an agent, i can
1. write to shellbrain
2. read from shellbrain

i encounter a problem. i want to see if there is any useful context in my shellbrain that will help me:
[1] solve the problem (case based reasoning)
[2] narrow my search in the solution space

at the interface layer, there should be language somewhere that says: always prioritize the code that you see as that is ground truth. the memories may be incorrect of have drifted.

okay, now, with the interface sketched out in language, i want to propose questions i have. some of these will be related to things we've already created in the @insights directory. some may be new questions. i ask that you do not hallucinate answers to the questions that are not in the @insights yet or not "associated" with things we've already discussed there to a reasonable degree. we'll come up with solutions to the other problems together. here are my questions. they won't be so structured. you'll need to structure them into one sentences in logical order.

1. okay, i encount a problem i want to consult my memory. so i draft a query to my memory. this query should be composed of 2 parts: [A] vector similarity, and choose those a few past a threshold. then for each that we pulled, we'll go down a "chain of associations", asking for the the most similar to the shellbrain pulled. we'll do this twice for each. so if there are 3 memories that where similar enough past the first query, we'll have up to 9 memories total, if subsequent ones made it past some threshold of similarity for those... we might have to add a decay on the threshold as we go further out. okay. that gets me some of my memories from vector similarity. cool. but it's possible that we still have blind spots. so we'll look for key word search too. that will be part [B]. we'll do both the associative cosine similarity and key word search (bounded amount) to give agent a merged set of the results from both [A] and [B]. merged to avoid redundancy and reduce tokens sent to AI.

okay, so what does that require? that requires a database to store:
1. the memories in plain text
2. the vector embeddings that map to the memories

so. what do we have so far?
1. interface for agent: query, write, dispute
2. recall engine (everything described above)
3. database

okay. now, how would we write? well... we have different types of memories:
1. procedural
2. user preferences
3. fact-based shellbrain
4. we also have episodic.... or, an immutable log for each repo

okay. it's also worth noting that the shellbrain will be hierarchical. the preferences for things (abstract) will be in the global memory. here, we might also include things like:
- what i'm working on 
- what my coding preferences are
- what my goals are

we may consider keeping higher level memories separate. maybe a separate table in the databse? maybe a different database altogher?

okay. so then. back to writing memories. how do we do that? well, i am the agent. so i will be working. i will have solved the problem after a few tries and iterations with the user. i will get a pretty clear picture of that problem from the back and forth with the user. also, if the conversation changes, i will always be able to read from my longterm shellbrain store. after we solve a problem, i should should run it by the user first like "i'm thinking about saving this shellbrain and categorizing it here" also "i'll save a global shellbrain here after you expressed that one preference". i, the user, will give the gohead. but, i don't always want to have to babysit the shellbrain storeing. i just want the shellbrain store to get better with usage. so there should be a setting somewhere where if enabled, the agent can just store a memory. but before it stores a memory. it should 
1. run the orginal query to see the original retreived memories
2. draft the new shellbrain and run a new query for that to make sure it's not already here
3. if nothing exists, then store it. 
4. if something exists and the shellbrain is like "redundant", then there should be some way to strengthen that memory. we can define "redundant" as the LLM's judgment. 
5. if something exists and anything is contradictory, there needs to be a way to get to ground truth. if it's a fact-based thing about the codebase, we trust the current version of the code more. here, what i think we can do is "weaken the score" or the contradictory memory. okay. so what did we just do? we introduced some notion of score of a memory, or "strength" of a memory. given that, should this score be a weight we apply to the vector after similarity is done? like... a truth score. like retrieval would be: [1] get that which is similar and then [2] rank not only by document similarity but in a linear combination of document similarity and truth score. or... maybe ranking is not even so necessary. maybe the LLM seeing the truth score is enough for it to excercise judment. but what is a truth score? does this need to be so mechanistic? i am now thinking, "man, is there even a way to really assign truth scores in a low-volume interaction engine like this?". now, i am thinking of something more similar... like a redit upvote/downvote system. here, memories can still be retrieved and given to the LLM ... but after a certain number of downvotes, we start filtering it out. it's almost like a reinforcement learning type thing... where we ask "which of these memories were helpful"? i think helpful is a better axis to assign scores on. why? because if something is not "true", then it was not "helpful" (e.g., the shellbrain contained stale information about the codebase). this way, the agent assigns a helpfulness upvote or down vote to each shellbrain that was retrieved at the end of each work session.

wait! but we actually need a distinction between memories! we need memories for all of the "problems" we worked on over time and we need memories for all of the "solutions", liked to those problems. now, when we do vector similarity and keyword search, i think it's important that we do this over the UNION of problems and solution embeddings. then, when we remember one, it automatically pulls the memory/memories associated. for example, it might have similarity with a problem... so it will auto pull the solutions asoociated with that problem. on the other hand, if it has similarity with a solution, it will pull the problems assoicated with that too. yes, i really like this. then, once it has all of those (pull from both [A] and [B]), it will merge to unique set of memories. so... this was actually kind of a breakthrough. because it means that we effectively store all of the problems that we ever worked on (as this robust backbone to pin things on) and their associated solutions... yes, i like this a lot.

okay, one more thing. we have the immutable episodic log, which is basically the agent notepad of what happened during the session. that means we should not only store what worked, we should also store what did not work. those failed attempts are not solutions, so they should be distinct from solutions, probably a separate table. but they should still link to problems in the same way solutions do. then, at the end of the session, the agent can look at its notes log plus shellbrain of the work and write both: what worked and what failed.
