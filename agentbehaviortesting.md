# Agent Behavior Testing

## Goal

Measure whether a revised Shellbrain skill changes agent behavior from:

- Shellbrain used mainly at session start
- Shellbrain used only when explicitly told

to:

- Shellbrain considered again during a session when the problem shifts
- Shellbrain used mid-session without the human reminding the agent
- `events` and closeout behavior staying healthy or improving

This is a behavior-change test, not a perfect semantic test. The question is not "did the agent use Shellbrain more?" The question is "did the agent use Shellbrain at better times?"

## What We Can Measure Already

Current telemetry already captures enough for a meaningful pre/post analysis:

- command-level Shellbrain invocations per repo/thread/session
- invocation timestamps
- read summaries
- read query text
- zero-result reads
- write summaries
- utility-vote writes
- guidance codes
- thread identity
- episode events and timestamps

This means we can retroactively compare behavior before and after a skill rollout without adding new infrastructure first.

## Recommended Evaluation Design

Use a simple pre/post analysis window:

- choose a clear deployment date for the new skill
- define a pre window and a post window
- compare the same repos, same host apps, and ideally similar task mixes

Prefer thread-level metrics over raw totals. A higher total read count alone does not prove better behavior.

## Primary Metrics

### 1. Mid-session reread rate

Fraction of threads with at least one `read` after the initial startup phase.

Possible thresholds:

- later than 10 minutes after the first Shellbrain command in the thread
- later than 15 minutes after the first Shellbrain command in the thread
- later than 30 minutes after the first Shellbrain command in the thread

Desired direction:

- increase

### 2. Multi-read thread rate

Fraction of threads with more than one `read`.

Desired direction:

- increase, but not explosively

### 3. Read-after-other-action rate

Fraction of threads where a `read` happens after some other Shellbrain action in the same thread, such as:

- `events`
- `create`
- `update`

This is a good proxy for "Shellbrain came back into the action set later."

Desired direction:

- increase

### 4. Read concentration at session start

Share of all reads that occur in the first startup window of a thread.

Desired direction:

- decrease

If the skill works, reads should become less concentrated at the very beginning of sessions.

### 5. Query sharpness

Review read query text before and after rollout.

Look for whether later reads are concrete and subproblem-specific rather than vague.

Desired direction:

- more concrete queries
- more subsystem / error / constraint specific queries

## Guardrail Metrics

These protect against a bad version of the rollout where agents start spamming Shellbrain.

### 6. Overtrigger rate

Look for signs of shallow rereads:

- many repeated reads in a very short burst
- many reads with nearly identical queries
- many zero-result reads

Desired direction:

- flat or down

### 7. Zero-result read rate

Already supported by current telemetry.

Desired direction:

- flat or down

If mid-session reads go up but zero-result reads spike, the skill may be causing spam instead of better timing.

### 8. Events-before-write compliance

Already supported by current telemetry.

Desired direction:

- flat or up

The new skill should not weaken disciplined write behavior.

### 9. Utility-vote followthrough

Already supported by current telemetry.

Desired direction:

- flat or up

If the skill makes agents re-engage Shellbrain more often, closeout behavior should not get worse.

## Useful Visualizations

The first useful plots are simple:

- histogram of time to second read within a thread
- histogram of gaps between reads
- per-thread timeline plots of `read`, `events`, `create`, and `update`
- pre/post comparison of startup-only threads vs mid-session reread threads

Even lightweight matplotlib output should be enough to spot whether reads are still sparse and front-loaded or are becoming more distributed over the life of a session.

## What We Cannot Measure Cleanly Yet

Current telemetry does not cleanly tell us:

- whether a true semantic subproblem shift happened
- whether the agent considered Shellbrain and explicitly decided to skip it
- whether a read happened at the "right" semantic moment

So the first analysis should be proxy-based, not overclaimed.

## Best Minimal Future Instrumentation

If stronger attribution is needed later, add one small signal:

- a checkpoint marker indicating the agent hit a Shellbrain decision point
- and whether it chose `read` or `skip`

That would make it much easier to measure whether the skill changes decision behavior instead of only changing observed command patterns.

This is useful, but should not block the first experiment.

## Recommended Interpretation

The rollout should be considered directionally successful if:

- more threads show meaningful mid-session rereads
- reads are less concentrated only at session start
- query sharpness improves or stays healthy
- zero-result reads do not materially worsen
- events-before-write compliance and utility-vote followthrough stay stable or improve

The rollout should be considered suspect if:

- read volume increases but timing does not change
- zero-result reads rise sharply
- repeated near-duplicate reads appear in short bursts
- write-discipline metrics worsen

## Practical Next Step

When this work resumes:

1. pick a deployment cutoff date
2. build one small analysis script over existing telemetry
3. generate a baseline pre/post report
4. only add new instrumentation if the proxy metrics are too ambiguous
