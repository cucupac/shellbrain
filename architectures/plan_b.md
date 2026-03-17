# Observational Memory: A Human-Inspired Memory System for AI Agents

At Mastra, we just shipped a new type of shellbrain for agentic systems: observational memory.
Observational shellbrain is text-based (no vector/graph DB needed), SoTA on benchmarks like LongMemEval, and compatible with Anthropic/OpenAI/etc prompt caching.
Even better: our implementation is open-source.
Compressing context to observations
If you step outside on a busy street, your brain processes millions of pixels, but distills down to one or two observations. That blue SUV just ran a red light. Your neighbor's pit bull is off their leash.
How it works
Observational shellbrain is designed to work the same way. In the context of a coding agent, it might compress a user session down to something like this:
plaintext
Date: 2026-01-15

🔴 12:10 User is building a Next.js app with Supabase auth, due in 1 week (meaning January 22nd 2026)
🔴 12:10 App uses server components with client-side hydration
🟡 12:12 User asked about middleware configuration for protected routes
🔴 12:15 User stated the app name is "Acme Dashboard"
Observations are log-based messages
The core message format resembles logs:
Formatted text, not structured objects. Down with knowledge graphs. Roon was right. Text is the universal interface. It's easier to use, optimized for LLMs, and far easier to debug.
A three-date model which we've seen perform better at temporal reasoning. This includes the observation date, referenced date, and relative date. Events are grouped by date with timestamps displayed inline.
Emoji-based prioritization. We're essentially using emojis to reimplement log levels. 
🔴 means important. 🟡 means maybe important.🟢 means info only.
Managing context: observations and raw messages
In observational memory, the context window is broken into two blocks.
The first block is the list of observations (like above). The second block is raw messages that haven't yet been compressed.
When new messages come in, they are appended to the end of the second block.
When it hits 30k tokens (the default threshold, though it's configurable), a separate "observer agent" compresses messages into new observations that are appended to the first block.
When observations hit 40k tokens (the default threshold, again configurable), a separate "reflector agent" garbage collects observations that don't matter.
Our token limit defaults are relatively conservative, providing SoTA results on benchmarks while staying well within context window limits.
This structure enables consistent prompt caching. Messages keep getting appended until the threshold is hit—full cache hits on every turn. When observation runs, messages are replaced with new observations appended to the existing observation block. The observation prefix stays consistent, so you still get a partial cache hit. Only during reflection (infrequent) is the entire cache invalidated.
Results
Mastra's new shellbrain system, Observational Memory, achieves 94.87% on LongMemEval with gpt-5-mini — over 3 points higher than any previously recorded score. With gpt-4o (the standard benchmark model), it scores 84.23%, beating the gpt-4o oracle (a configuration given only the conversations containing the answer) by 2 points, and the previous gpt-4o SOTA from Supershellbrain by 2.6 points.
These scores were achieved with a completely stable context window. The context is predictable, reproducible, and fully prompt-cacheable. See the full research breakdown.
Benchmark table comparing long-term shellbrain systems by model and LongMemEval score, showing Mastra OM results leading across multiple models.
* EmergenceMem's 86.00% is reported for an "Internal" configuration and is not publicly reproducible. Both EmergenceMem and Hindsight use multi-stage retrieval and neural reranking; OM uses a single pass with a stable context window.
Full per-category breakdowns and methodology are in the research page.
Mastra's New Memory System
I've been working on shellbrain at Mastra for the last year. We shipped working shellbrain and semantic recall in March and April before "context engineering" was a thing.
Working shellbrain provided moderate lifts to benchmarks and was cacheable, while semantic recall provided larger lifts but was not.
Then context engineering became a thing. We noticed that a lot of our users were getting their whole context windows blown up by tool call results. Other users brought up wanting to aggressively cache using Anthropic, OpenAI, and other providers to reduce token costs.
This problem was compounded with newer types of parallelizable agents that generate huge amounts of context very quickly. Browser agents using Playwright and screenshotting pages. Coding agents scanning files and executing commands. Deep research agents browsing multiple URLs in parallel.
In some ways observational shellbrain is the child of working shellbrain and semantic recall. We're considering this the new primary Mastra shellbrain system and encouraging users to migrate over.
Current limitations
Observation currently runs synchronously — when the token threshold is hit, the conversation blocks while the Observer processes messages. We've solved this with an async background buffering mode that runs observation outside the conversation loop and we're shipping it this week.
Get started now
typescript
import { Memory } from "@mastra/memory";
import { Agent } from "@mastra/core/agent";

export const agent = new Agent({
  name: "om-agent",
  instructions: "You are a helpful assistant.",
  model: "openai/gpt-5-mini",
  memory: new Memory({
    options: {
      observationalMemory: true,
    },
  }),
});


# Observational Memory

**Added in:** `@mastra/memory@1.1.0`

Observational Memory (OM) is Mastra's shellbrain system for long-context agentic memory. Two background agents — an **Observer** and a **Reflector** — watch your agent's conversations and maintain a dense observation log that replaces raw message history as it grows.

## Quick Start

Enable `observationalMemory` in the shellbrain options when creating your agent:

```typescript
import { Memory } from "@mastra/memory";
import { Agent } from "@mastra/core/agent";

export const agent = new Agent({
  name: "my-agent",
  instructions: "You are a helpful assistant.",
  model: "openai/gpt-5-mini",
  memory: new Memory({
    options: {
      observationalMemory: true,
    },
  }),
});
```

That's it. The agent now has humanlike long-term shellbrain that persists across conversations. Setting `observationalMemory: true` uses `google/gemini-2.5-flash` by default. To use a different model or customize thresholds, pass a config object instead:

```typescript
const shellbrain = new Memory({
  options: {
    observationalMemory: {
      model: "deepseek/deepseek-reasoner",
    },
  },
});
```

See [configuration options](https://mastra.ai/reference/memory/observational-memory) for full API details.

> **Note:** OM currently only supports `@mastra/pg`, `@mastra/libsql`, and `@mastra/mongodb` storage adapters. It uses background agents for managing memory. When using `observationalMemory: true`, the default model is `google/gemini-2.5-flash`. When passing a config object, a `model` must be explicitly set.

## Benefits

- **Prompt caching**: OM's context is stable — observations append over time rather than being dynamically retrieved each turn. This keeps the prompt prefix cacheable, which reduces costs.
- **Compression**: Raw message history and tool results get compressed into a dense observation log. Smaller context means faster responses and longer coherent conversations.
- **Zero context rot**: The agent sees relevant information instead of noisy tool calls and irrelevant tokens, so the agent stays on task over long sessions.

## How It Works

You don't remember every word of every conversation you've ever had. You observe what happened subconsciously, then your brain reflects — reorganizing, combining, and condensing into long-term memory. OM works the same way.

Every time an agent responds, it sees a context window containing its system prompt, recent message history, and any injected context. The context window is finite — even models with large token limits perform worse when the window is full. This causes two problems:

- **Context rot**: the more raw message history an agent carries, the worse it performs.
- **Context waste**: most of that history contains tokens no longer needed to keep the agent on task.

OM solves both problems by compressing old context into dense observations.

### Observations

When message history tokens exceed a threshold (default: 30,000), the Observer creates observations — concise notes about what happened:

```text
Date: 2026-01-15
- 🔴 12:10 User is building a Next.js app with Supabase auth, due in 1 week (meaning January 22nd 2026)
  - 🔴 12:10 App uses server components with client-side hydration
  - 🟡 12:12 User asked about middleware configuration for protected routes
  - 🔴 12:15 User stated the app name is "Acme Dashboard"
```

The compression is typically 5–40×. The Observer also tracks a **current task** and **suggested response** so the agent picks up where it left off.

Example: an agent using Playwright MCP might see 50,000+ tokens per page snapshot. With OM, the Observer watches the interaction and creates a few hundred tokens of observations about what was on the page and what actions were taken. The agent stays on task without carrying every raw snapshot.

### Reflections

When observations exceed their threshold (default: 40,000 tokens), the Reflector condenses them — combining related items and reflecting on patterns.

The result is a three-tier system:

1. **Recent messages**: Exact conversation history for the current task
2. **Observations**: A log of what the Observer has seen
3. **Reflections**: Condensed observations when shellbrain becomes too long

## Models

The Observer and Reflector run in the background. Any model that works with Mastra's model routing (e.g. `openai/...`, `google/...`, `deepseek/...`) can be used.

When using `observationalMemory: true`, the default model is `google/gemini-2.5-flash`. When passing a config object, a `model` must be explicitly set.

We recommend `google/gemini-2.5-flash` — it works well for both observation and reflection, and its 1M token context window gives the Reflector headroom.

We've also tested `deepseek`, `qwen3`, and `glm-4.7` for the Observer. For the Reflector, make sure the model's context window can fit all observations. Note that Claude 4.5 models currently don't work well as observer or reflector.

```typescript
const shellbrain = new Memory({
  options: {
    observationalMemory: {
      model: "deepseek/deepseek-reasoner",
    },
  },
});
```

See [model configuration](https://mastra.ai/reference/memory/observational-memory) for using different models per agent.

## Scopes

### Thread scope (default)

Each thread has its own observations. This scope is well tested and works well as a general purpose shellbrain system, especially for long horizon agentic use-cases.

```typescript
const shellbrain = new Memory({
  options: {
    observationalMemory: {
      model: "google/gemini-2.5-flash",
      scope: "thread",
    },
  },
});
```

### Resource scope (experimental)

Observations are shared across all threads for a resource (typically a user). Enables cross-conversation memory.

```typescript
const shellbrain = new Memory({
  options: {
    observationalMemory: {
      model: "google/gemini-2.5-flash",
      scope: "resource",
    },
  },
});
```

Resource scope works, however it's marked as experimental for now until we prove task adherence/continuity across multiple ongoing simultaneous threads. As of today, you may need to tweak your system prompt to prevent one thread from continuing the work that another had already started (but hadn't finished).

This is because in resource scope, each thread is a perspective on _all_ threads for the resource.

For your use-case this may not be a problem, so your mileage may vary.

> **Warning:** In resource scope, unobserved messages across _all_ threads are processed together. For users with many existing threads, this can be slow. Use thread scope for existing apps.

## Token Budgets

OM uses token thresholds to decide when to observe and reflect. See [token budget configuration](https://mastra.ai/reference/memory/observational-memory) for details.

```typescript
const shellbrain = new Memory({
  options: {
    observationalMemory: {
      model: "google/gemini-2.5-flash",
      observation: {
        // when to run the Observer (default: 30,000)
        messageTokens: 30_000,
      },
      reflection: {
        // when to run the Reflector (default: 40,000)
        observationTokens: 40_000,
      },
      // let message history borrow from observation budget
      // requires bufferTokens: false (temporary limitation)
      shareTokenBudget: false,
    },
  },
});
```

## Async Buffering

Without async buffering, the Observer runs synchronously when the message threshold is reached — the agent pauses mid-conversation while the Observer LLM call completes. With async buffering (enabled by default), observations are pre-computed in the background as the conversation grows. When the threshold is hit, buffered observations activate instantly with no pause.

### How it works

As the agent converses, message tokens accumulate. At regular intervals (`bufferTokens`), a background Observer call runs without blocking the agent. Each call produces a "chunk" of observations that's stored in a buffer.

When message tokens reach the `messageTokens` threshold, buffered chunks activate: their observations move into the active observation log, and the corresponding raw messages are removed from the context window. The agent never pauses.

If the agent produces messages faster than the Observer can process them, a `blockAfter` safety threshold forces a synchronous observation as a last resort.

Reflection works similarly — the Reflector runs in the background when observations reach a fraction of the reflection threshold.

### Settings

| Setting                        | Default | What it controls                                                                                                                                                                      |
| ------------------------------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `observation.bufferTokens`     | `0.2`   | How often to buffer. `0.2` means every 20% of `messageTokens` — with the default 30k threshold, that's roughly every 6k tokens. Can also be an absolute token count (e.g. `5000`).    |
| `observation.bufferActivation` | `0.8`   | How aggressively to clear the message window on activation. `0.8` means remove enough messages to keep only 20% of `messageTokens` remaining. Lower values keep more message history. |
| `observation.blockAfter`       | `1.2`   | Safety threshold as a multiplier of `messageTokens`. At `1.2`, synchronous observation is forced at 36k tokens (1.2 × 30k). Only matters if buffering can't keep up.                  |
| `reflection.bufferActivation`  | `0.5`   | When to start background reflection. `0.5` means reflection begins when observations reach 50% of the `observationTokens` threshold.                                                  |
| `reflection.blockAfter`        | `1.2`   | Safety threshold for reflection, same logic as observation.                                                                                                                           |

### Disabling

To disable async buffering and use synchronous observation/reflection instead:

```typescript
const shellbrain = new Memory({
  options: {
    observationalMemory: {
      model: "google/gemini-2.5-flash",
      observation: {
        bufferTokens: false,
      },
    },
  },
});
```

Setting `bufferTokens: false` disables both observation and reflection async buffering. See [async buffering configuration](https://mastra.ai/reference/memory/observational-memory) for the full API.

> **Note:** Async buffering is not supported with `scope: 'resource'`. It is automatically disabled in resource scope.

## Migrating existing threads

No manual migration needed. OM reads existing messages and observes them lazily when thresholds are exceeded.

- **Thread scope**: The first time a thread exceeds `observation.messageTokens`, the Observer processes the backlog.
- **Resource scope**: All unobserved messages across all threads for a resource are processed together. For users with many existing threads, this could take significant time.

## Viewing in Mastra Studio

Mastra Studio shows OM status in real time in the shellbrain tab: token usage, which model is running, current observations, and reflection history.

## Comparing OM with other shellbrain features

- **[Message history](https://mastra.ai/docs/memory/message-history)**: High-fidelity record of the current conversation
- **[Working memory](https://mastra.ai/docs/memory/working-memory)**: Small, structured state (JSON or markdown) for user preferences, names, goals
- **[Semantic Recall](https://mastra.ai/docs/memory/semantic-recall)**: RAG-based retrieval of relevant past messages

If you're using working shellbrain to store conversation summaries or ongoing state that grows over time, OM is a better fit. Working shellbrain is for small, structured data; OM is for long-running event logs. OM also manages message history automatically—the `messageTokens` setting controls how much raw history remains before observation runs.

In practical terms, OM replaces both working shellbrain and message history, and has greater accuracy (and lower cost) than Semantic Recall.

## Related

- [Observational Memory Reference](https://mastra.ai/reference/memory/observational-memory)
- [Memory Overview](https://mastra.ai/docs/memory/overview)
- [Message History](https://mastra.ai/docs/memory/message-history)
- [Memory Processors](https://mastra.ai/docs/memory/memory-processors)


# Observational Memory

**Added in:** `@mastra/memory@1.1.0`

Observational Memory (OM) is Mastra's shellbrain system for long-context agentic memory. Two background agents — an **Observer** that watches conversations and creates observations, and a **Reflector** that restructures observations by combining related items, reflecting on overarching patterns, and condensing where possible — maintain an observation log that replaces raw message history as it grows.

## Usage

```typescript
import { Memory } from "@mastra/memory";
import { Agent } from "@mastra/core/agent";

export const agent = new Agent({
  name: "my-agent",
  instructions: "You are a helpful assistant.",
  model: "openai/gpt-5-mini",
  memory: new Memory({
    options: {
      observationalMemory: true,
    },
  }),
});
```

## Configuration

The `observationalMemory` option accepts `true`, a configuration object, or `false`. Setting `true` enables OM with `google/gemini-2.5-flash` as the default model. When passing a config object, a `model` must be explicitly set — either at the top level, or on `observation.model` and/or `reflection.model`.

**enabled?:** (`boolean`): Enable or disable Observational Memory. When omitted from a config object, defaults to \`true\`. Only \`enabled: false\` explicitly disables it. (Default: `true`)

**model?:** (`string | LanguageModel | DynamicModel | ModelWithRetries[]`): Model for both the Observer and Reflector agents. Sets the model for both at once. Cannot be used together with \`observation.model\` or \`reflection.model\` — an error will be thrown if both are set. When using \`observationalMemory: true\`, defaults to \`google/gemini-2.5-flash\`. When passing a config object, this or \`observation.model\`/\`reflection.model\` must be set. Use \`"default"\` to explicitly use the default model (\`google/gemini-2.5-flash\`). (Default: `'google/gemini-2.5-flash' (when using observationalMemory: true)`)

**scope?:** (`'resource' | 'thread'`): Memory scope for observations. \`'thread'\` keeps observations per-thread. \`'resource'\` (experimental) shares observations across all threads for a resource, enabling cross-conversation memory. (Default: `'thread'`)

**shareTokenBudget?:** (`boolean`): Share the token budget between messages and observations. When enabled, the total budget is \`observation.messageTokens + reflection.observationTokens\`. Messages can use more space when observations are small, and vice versa. This maximizes context usage through flexible allocation. \*\*Note:\*\* \`shareTokenBudget\` is not yet compatible with async buffering. You must set \`observation: { bufferTokens: false }\` when using this option (this is a temporary limitation). (Default: `false`)

**observation?:** (`ObservationalMemoryObservationConfig`): Configuration for the observation step. Controls when the Observer agent runs and how it behaves.

**reflection?:** (`ObservationalMemoryReflectionConfig`): Configuration for the reflection step. Controls when the Reflector agent runs and how it behaves.

### Observation config

**model?:** (`string | LanguageModel | DynamicModel | ModelWithRetries[]`): Model for the Observer agent. Cannot be set if a top-level \`model\` is also provided. If neither this nor the top-level \`model\` is set, falls back to \`reflection.model\`.

**messageTokens?:** (`number`): Token count of unobserved messages that triggers observation. When unobserved message tokens exceed this threshold, the Observer agent is called. (Default: `30000`)

**maxTokensPerBatch?:** (`number`): Maximum tokens per batch when observing multiple threads in resource scope. Threads are chunked into batches of this size and processed in parallel. Lower values mean more parallelism but more API calls. (Default: `10000`)

**modelSettings?:** (`ObservationalMemoryModelSettings`): Model settings for the Observer agent. (Default: `{ temperature: 0.3, maxOutputTokens: 100_000 }`)

**bufferTokens?:** (`number | false`): Token interval for async background observation buffering. Can be an absolute token count (e.g. \`5000\`) or a fraction of \`messageTokens\` (e.g. \`0.25\` = buffer every 25% of threshold). When set, observations run in the background at this interval, storing results in a buffer. When the main \`messageTokens\` threshold is reached, buffered observations activate instantly without a blocking LLM call. Must resolve to less than \`messageTokens\`. Set to \`false\` to explicitly disable all async buffering (both observation and reflection). (Default: `0.2`)

**bufferActivation?:** (`number`): Ratio (0-1) controlling how much of the message window to retain after activation. For example, \`0.8\` means activate enough to keep only 20% of \`messageTokens\` remaining. Higher values remove more message history per activation. (Default: `0.8`)

**blockAfter?:** (`number`): Token threshold above which synchronous (blocking) observation is forced. Between \`messageTokens\` and \`blockAfter\`, only async buffering/activation is used. Above \`blockAfter\`, a synchronous observation runs as a last resort. Accepts a multiplier (1 < value < 2, multiplied by \`messageTokens\`) or an absolute token count (≥ 2, must be greater than \`messageTokens\`). Only relevant when \`bufferTokens\` is set. Defaults to \`1.2\` when async buffering is enabled. (Default: `1.2 (when bufferTokens is set)`)

### Reflection config

**model?:** (`string | LanguageModel | DynamicModel | ModelWithRetries[]`): Model for the Reflector agent. Cannot be set if a top-level \`model\` is also provided. If neither this nor the top-level \`model\` is set, falls back to \`observation.model\`.

**observationTokens?:** (`number`): Token count of observations that triggers reflection. When observation tokens exceed this threshold, the Reflector agent is called to condense them. (Default: `40000`)

**modelSettings?:** (`ObservationalMemoryModelSettings`): Model settings for the Reflector agent. (Default: `{ temperature: 0, maxOutputTokens: 100_000 }`)

**bufferActivation?:** (`number`): Ratio (0-1) controlling when async reflection buffering starts. When observation tokens reach \`observationTokens \* bufferActivation\`, reflection runs in the background. On activation at the full threshold, the buffered reflection replaces the observations it covers, preserving any new observations appended after that range. (Default: `0.5`)

**blockAfter?:** (`number`): Token threshold above which synchronous (blocking) reflection is forced. Between \`observationTokens\` and \`blockAfter\`, only async buffering/activation is used. Above \`blockAfter\`, a synchronous reflection runs as a last resort. Accepts a multiplier (1 < value < 2, multiplied by \`observationTokens\`) or an absolute token count (≥ 2, must be greater than \`observationTokens\`). Only relevant when \`bufferActivation\` is set. Defaults to \`1.2\` when async reflection is enabled. (Default: `1.2 (when bufferActivation is set)`)

### Model settings

**temperature?:** (`number`): Temperature for generation. Lower values produce more consistent output. (Default: `0.3`)

**maxOutputTokens?:** (`number`): Maximum output tokens. Set high to prevent truncation of observations. (Default: `100000`)

## Examples

### Resource scope with custom thresholds (experimental)

```typescript
import { Memory } from "@mastra/memory";
import { Agent } from "@mastra/core/agent";

export const agent = new Agent({
  name: "my-agent",
  instructions: "You are a helpful assistant.",
  model: "openai/gpt-5-mini",
  memory: new Memory({
    options: {
      observationalMemory: {
        model: "google/gemini-2.5-flash",
        scope: "resource",
        observation: {
          messageTokens: 20_000,
        },
        reflection: {
          observationTokens: 60_000,
        },
      },
    },
  }),
});
```

### Shared token budget

```typescript
import { Memory } from "@mastra/memory";
import { Agent } from "@mastra/core/agent";

export const agent = new Agent({
  name: "my-agent",
  instructions: "You are a helpful assistant.",
  model: "openai/gpt-5-mini",
  memory: new Memory({
    options: {
      observationalMemory: {
        shareTokenBudget: true,
        observation: {
          messageTokens: 20_000,
          bufferTokens: false, // required when using shareTokenBudget (temporary limitation)
        },
        reflection: {
          observationTokens: 80_000,
        },
      },
    },
  }),
});
```

When `shareTokenBudget` is enabled, the total budget is `observation.messageTokens + reflection.observationTokens` (100k in this example). If observations only use 30k tokens, messages can expand to use up to 70k. If messages are short, observations have more room before triggering reflection.

### Custom model

```typescript
import { Memory } from "@mastra/memory";
import { Agent } from "@mastra/core/agent";

export const agent = new Agent({
  name: "my-agent",
  instructions: "You are a helpful assistant.",
  model: "openai/gpt-5-mini",
  memory: new Memory({
    options: {
      observationalMemory: {
        model: "openai/gpt-4o-mini",
      },
    },
  }),
});
```

### Different models per agent

```typescript
import { Memory } from "@mastra/memory";
import { Agent } from "@mastra/core/agent";

export const agent = new Agent({
  name: "my-agent",
  instructions: "You are a helpful assistant.",
  model: "openai/gpt-5-mini",
  memory: new Memory({
    options: {
      observationalMemory: {
        observation: {
          model: "google/gemini-2.5-flash",
        },
        reflection: {
          model: "openai/gpt-4o-mini",
        },
      },
    },
  }),
});
```

### Async buffering

Async buffering is **enabled by default**. It pre-computes observations in the background as the conversation grows — when the `messageTokens` threshold is reached, buffered observations activate instantly with no blocking LLM call.

The lifecycle is: **buffer → activate → remove messages → repeat**. Background Observer calls run at `bufferTokens` intervals, each producing a chunk of observations. At threshold, chunks activate: observations move into the log, raw messages are removed from context. The `blockAfter` threshold forces a synchronous fallback if buffering can't keep up.

Default settings:

- `observation.bufferTokens: 0.2` — buffer every 20% of `messageTokens` (e.g. every \~6k tokens with a 30k threshold)
- `observation.bufferActivation: 0.8` — on activation, remove enough messages to keep only 20% of the threshold remaining
- `reflection.bufferActivation: 0.5` — start background reflection at 50% of observation threshold

To customize:

```typescript
import { Memory } from "@mastra/memory";
import { Agent } from "@mastra/core/agent";

export const agent = new Agent({
  name: "my-agent",
  instructions: "You are a helpful assistant.",
  model: "openai/gpt-5-mini",
  memory: new Memory({
    options: {
      observationalMemory: {
        model: "google/gemini-2.5-flash",
        observation: {
          messageTokens: 30_000,
          // Buffer every 5k tokens (runs in background)
          bufferTokens: 5_000,
          // Activate to retain 30% of threshold
          bufferActivation: 0.7,
          // Force synchronous observation at 1.5x threshold
          blockAfter: 1.5,
        },
        reflection: {
          observationTokens: 60_000,
          // Start background reflection at 50% of threshold
          bufferActivation: 0.5,
          // Force synchronous reflection at 1.2x threshold
          blockAfter: 1.2,
        },
      },
    },
  }),
});
```

To disable async buffering entirely:

```typescript
observationalMemory: {
  model: "google/gemini-2.5-flash",
  observation: {
    bufferTokens: false,
  },
}
```

Setting `bufferTokens: false` disables both observation and reflection async buffering. Observations and reflections will run synchronously when their thresholds are reached.

> **Note:** Async buffering is not supported with `scope: 'resource'` and is automatically disabled in resource scope.

## Streaming data parts

Observational Memory emits typed data parts during agent execution that clients can use for real-time UI feedback. These are streamed alongside the agent's response.

### `data-om-status`

Emitted once per agent loop step, before model generation. Provides a snapshot of the current shellbrain state, including token usage for both context windows and the state of any async buffered content.

```typescript
interface DataOmStatusPart {
  type: 'data-om-status';
  data: {
    windows: {
      active: {
        /** Unobserved message tokens and the threshold that triggers observation */
        messages: { tokens: number; threshold: number };
        /** Observation tokens and the threshold that triggers reflection */
        observations: { tokens: number; threshold: number };
      };
      buffered: {
        observations: {
          /** Number of buffered chunks staged for activation */
          chunks: number;
          /** Total message tokens across all buffered chunks */
          messageTokens: number;
          /** Projected message tokens that would be removed if activation happened now (based on bufferActivation ratio and chunk boundaries) */
          projectedMessageRemoval: number;
          /** Observation tokens that will be added on activation */
          observationTokens: number;
          /** idle: no buffering in progress. running: background observer is working. complete: chunks are ready for activation. */
          status: 'idle' | 'running' | 'complete';
        };
        reflection: {
          /** Observation tokens that were fed into the reflector (pre-compression size) */
          inputObservationTokens: number;
          /** Observation tokens the reflection will produce on activation (post-compression size) */
          observationTokens: number;
          /** idle: no reflection buffered. running: background reflector is working. complete: reflection is ready for activation. */
          status: 'idle' | 'running' | 'complete';
        };
      };
    };
    recordId: string;
    threadId: string;
    stepNumber: number;
    /** Increments each time the Reflector creates a new generation */
    generationCount: number;
  };
}
```

`buffered.reflection.inputObservationTokens` is the size of the observations that were sent to the Reflector. `buffered.reflection.observationTokens` is the compressed result — the size of what will replace those observations when the reflection activates. A client can use these two values to show a compression ratio.

Clients can derive percentages and post-activation estimates from the raw values:

```typescript
// Message window usage %
const msgPercent = status.windows.active.messages.tokens
  / status.windows.active.messages.threshold;

// Observation window usage %
const obsPercent = status.windows.active.observations.tokens
  / status.windows.active.observations.threshold;

// Projected message tokens after buffered observations activate
// Uses projectedMessageRemoval which accounts for bufferActivation ratio and chunk boundaries
const postActivation = status.windows.active.messages.tokens
  - status.windows.buffered.observations.projectedMessageRemoval;

// Reflection compression ratio (when buffered reflection exists)
const { inputObservationTokens, observationTokens } = status.windows.buffered.reflection;
if (inputObservationTokens > 0) {
  const compressionRatio = observationTokens / inputObservationTokens;
}
```

### `data-om-observation-start`

Emitted when the Observer or Reflector agent begins processing.

**cycleId:** (`string`): Unique ID for this cycle — shared between start/end/failed markers.

**operationType:** (`'observation' | 'reflection'`): Whether this is an observation or reflection operation.

**startedAt:** (`string`): ISO timestamp when processing started.

**tokensToObserve:** (`number`): Message tokens (input) being processed in this batch.

**recordId:** (`string`): The OM record ID.

**threadId:** (`string`): This thread's ID.

**threadIds:** (`string[]`): All thread IDs in this batch (for resource-scoped).

**config:** (`ObservationMarkerConfig`): Snapshot of \`messageTokens\`, \`observationTokens\`, and \`scope\` at observation time.

### `data-om-observation-end`

Emitted when observation or reflection completes successfully.

**cycleId:** (`string`): Matches the corresponding \`start\` marker.

**operationType:** (`'observation' | 'reflection'`): Type of operation that completed.

**completedAt:** (`string`): ISO timestamp when processing completed.

**durationMs:** (`number`): Duration in milliseconds.

**tokensObserved:** (`number`): Message tokens (input) that were processed.

**observationTokens:** (`number`): Resulting observation tokens (output) after the Observer compressed them.

**observations?:** (`string`): The generated observations text.

**currentTask?:** (`string`): Current task extracted by the Observer.

**suggestedResponse?:** (`string`): Suggested response extracted by the Observer.

**recordId:** (`string`): The OM record ID.

**threadId:** (`string`): This thread's ID.

### `data-om-observation-failed`

Emitted when observation or reflection fails. The system falls back to synchronous processing.

**cycleId:** (`string`): Matches the corresponding \`start\` marker.

**operationType:** (`'observation' | 'reflection'`): Type of operation that failed.

**failedAt:** (`string`): ISO timestamp when the failure occurred.

**durationMs:** (`number`): Duration until failure in milliseconds.

**tokensAttempted:** (`number`): Message tokens (input) that were attempted.

**error:** (`string`): Error message.

**observations?:** (`string`): Any partial content available for display.

**recordId:** (`string`): The OM record ID.

**threadId:** (`string`): This thread's ID.

### `data-om-buffering-start`

Emitted when async buffering begins in the background. Buffering pre-computes observations or reflections before the main threshold is reached.

**cycleId:** (`string`): Unique ID for this buffering cycle.

**operationType:** (`'observation' | 'reflection'`): Type of operation being buffered.

**startedAt:** (`string`): ISO timestamp when buffering started.

**tokensToBuffer:** (`number`): Message tokens (input) being buffered in this cycle.

**recordId:** (`string`): The OM record ID.

**threadId:** (`string`): This thread's ID.

**threadIds:** (`string[]`): All thread IDs being buffered (for resource-scoped).

**config:** (`ObservationMarkerConfig`): Snapshot of config at buffering time.

### `data-om-buffering-end`

Emitted when async buffering completes. The content is stored but not yet activated in the main context.

**cycleId:** (`string`): Matches the corresponding \`buffering-start\` marker.

**operationType:** (`'observation' | 'reflection'`): Type of operation that was buffered.

**completedAt:** (`string`): ISO timestamp when buffering completed.

**durationMs:** (`number`): Duration in milliseconds.

**tokensBuffered:** (`number`): Message tokens (input) that were buffered.

**bufferedTokens:** (`number`): Observation tokens (output) after the Observer compressed them.

**observations?:** (`string`): The buffered content.

**recordId:** (`string`): The OM record ID.

**threadId:** (`string`): This thread's ID.

### `data-om-buffering-failed`

Emitted when async buffering fails. The system falls back to synchronous processing when the threshold is reached.

**cycleId:** (`string`): Matches the corresponding \`buffering-start\` marker.

**operationType:** (`'observation' | 'reflection'`): Type of operation that failed.

**failedAt:** (`string`): ISO timestamp when the failure occurred.

**durationMs:** (`number`): Duration until failure in milliseconds.

**tokensAttempted:** (`number`): Message tokens (input) that were attempted to buffer.

**error:** (`string`): Error message.

**observations?:** (`string`): Any partial content.

**recordId:** (`string`): The OM record ID.

**threadId:** (`string`): This thread's ID.

### `data-om-activation`

Emitted when buffered observations or reflections are activated (moved into the active context window). This is an instant operation — no LLM call is involved.

**cycleId:** (`string`): Unique ID for this activation event.

**operationType:** (`'observation' | 'reflection'`): Type of content activated.

**activatedAt:** (`string`): ISO timestamp when activation occurred.

**chunksActivated:** (`number`): Number of buffered chunks activated.

**tokensActivated:** (`number`): Message tokens (input) from activated chunks. For observation activation, these are removed from the message window. For reflection activation, this is the observation tokens that were compressed.

**observationTokens:** (`number`): Resulting observation tokens after activation.

**messagesActivated:** (`number`): Number of messages that were observed via activation.

**generationCount:** (`number`): Current reflection generation count.

**observations?:** (`string`): The activated observations text.

**recordId:** (`string`): The OM record ID.

**threadId:** (`string`): This thread's ID.

**config:** (`ObservationMarkerConfig`): Snapshot of config at activation time.

## Standalone usage

Most users should use the `Memory` class above. Using `ObservationalMemory` directly is mainly useful for benchmarking, experimentation, or when you need to control processor ordering with other processors (like [guardrails](https://mastra.ai/docs/agents/guardrails)).

```typescript
import { ObservationalMemory } from "@mastra/memory/processors";
import { Agent } from "@mastra/core/agent";
import { LibSQLStore } from "@mastra/libsql";

const storage = new LibSQLStore({
  id: "my-storage",
  url: "file:./memory.db",
});

const om = new ObservationalMemory({
  storage: storage.stores.shellbrain,
  model: "google/gemini-2.5-flash",
  scope: "resource",
  observation: {
    messageTokens: 20_000,
  },
  reflection: {
    observationTokens: 60_000,
  },
});

export const agent = new Agent({
  name: "my-agent",
  instructions: "You are a helpful assistant.",
  model: "openai/gpt-5-mini",
  inputProcessors: [om],
  outputProcessors: [om],
});
```

### Standalone config

The standalone `ObservationalMemory` class accepts all the same options as the `observationalMemory` config object above, plus the following:

**storage:** (`MemoryStorage`): Storage adapter for persisting observations. Must be a MemoryStorage instance (from \`MastraStorage.stores.shellbrain\`).

**onDebugEvent?:** (`(event: ObservationDebugEvent) => void`): Debug callback for observation events. Called whenever observation-related events occur. Useful for debugging and understanding the observation flow.

**obscureThreadIds?:** (`boolean`): When enabled, thread IDs are hashed before being included in observation context. This prevents the LLM from recognizing patterns in thread identifiers. Automatically enabled when using resource scope through the Memory class. (Default: `false`)

### Related

- [Observational Memory](https://mastra.ai/docs/memory/observational-memory)
- [Memory Overview](https://mastra.ai/docs/memory/overview)
- [Memory Class](https://mastra.ai/reference/memory/memory-class)
- [Memory Processors](https://mastra.ai/docs/memory/memory-processors)
- [Processors](https://mastra.ai/docs/agents/processors)


# Memory

Memory enables your agent to remember user messages, agent replies, and tool results across interactions, giving it the context it needs to stay consistent, maintain conversation flow, and produce better answers over time.

Mastra supports four complementary shellbrain types:

- [**Message history**](https://mastra.ai/docs/memory/message-history) - keeps recent messages from the current conversation so they can be rendered in the UI and used to maintain short-term continuity within the exchange.
- [**Working memory**](https://mastra.ai/docs/memory/working-memory) - stores persistent, structured user data such as names, preferences, and goals.
- [**Semantic recall**](https://mastra.ai/docs/memory/semantic-recall) - retrieves relevant messages from older conversations based on semantic meaning rather than exact keywords, mirroring how humans recall information by association. Requires a [vector database](https://mastra.ai/docs/memory/semantic-recall) and an [embedding model](https://mastra.ai/docs/memory/semantic-recall).
- [**Observational memory**](https://mastra.ai/docs/memory/observational-memory) - uses background Observer and Reflector agents to maintain a dense observation log that replaces raw message history as it grows, keeping the context window small while preserving long-term shellbrain across conversations.

If the combined shellbrain exceeds the model's context limit, [shellbrain processors](https://mastra.ai/docs/memory/memory-processors) can filter, trim, or prioritize content so the most relevant information is preserved.

## Getting started

Choose a shellbrain option to get started:

- [Message history](https://mastra.ai/docs/memory/message-history)
- [Working memory](https://mastra.ai/docs/memory/working-memory)
- [Semantic recall](https://mastra.ai/docs/memory/semantic-recall)
- [Observational memory](https://mastra.ai/docs/memory/observational-memory)

## Storage

Before enabling memory, you must first configure a storage adapter. Mastra supports several databases including PostgreSQL, MongoDB, libSQL, and [more](https://mastra.ai/docs/memory/storage).

Storage can be configured at the [instance level](https://mastra.ai/docs/memory/storage) (shared across all agents) or at the [agent level](https://mastra.ai/docs/memory/storage) (dedicated per agent).

For semantic recall, you can use a separate vector database like Pinecone alongside your primary storage.

See the [Storage](https://mastra.ai/docs/memory/storage) documentation for configuration options, supported providers, and examples.

## Debugging shellbrain

When [tracing](https://mastra.ai/docs/observability/tracing/overview) is enabled, you can inspect exactly which messages the agent uses for context in each request. The trace output shows all shellbrain included in the agent's context window - both recent message history and messages recalled via semantic recall.

![Trace output showing shellbrain context included in an agent request](https://mastra.ai/_next/image?url=%2Ftracingafter.png\&w=1920\&q=75)

This visibility helps you understand why an agent made specific decisions and verify that shellbrain retrieval is working as expected.

## Next steps

- Learn more about [Storage](https://mastra.ai/docs/memory/storage) providers and configuration options
- Add [Message history](https://mastra.ai/docs/memory/message-history), [Working memory](https://mastra.ai/docs/memory/working-memory), [Semantic recall](https://mastra.ai/docs/memory/semantic-recall), or [Observational memory](https://mastra.ai/docs/memory/observational-memory)
- Visit [Memory configuration reference](https://mastra.ai/reference/memory/memory-class) for all available options


# Memory Class

The `Memory` class provides a robust system for managing conversation history and thread-based message storage in Mastra. It enables persistent storage of conversations, semantic search capabilities, and efficient message retrieval. You must configure a storage provider for conversation history, and if you enable semantic recall you will also need to provide a vector store and embedder.

## Usage example

```typescript
import { Memory } from "@mastra/memory";
import { Agent } from "@mastra/core/agent";

export const agent = new Agent({
  name: "test-agent",
  instructions: "You are an agent with memory.",
  model: "openai/gpt-5.1",
  memory: new Memory({
    options: {
      workingMemory: {
        enabled: true,
      },
    },
  }),
});
```

> To enable `workingMemory` on an agent, you’ll need a storage provider configured on your main Mastra instance. See [Mastra class](https://mastra.ai/reference/core/mastra-class) for more information.

## Constructor parameters

**storage?:** (`MastraCompositeStore`): Storage implementation for persisting shellbrain data. Defaults to \`new DefaultStorage({ config: { url: "file:memory.db" } })\` if not provided.

**vector?:** (`MastraVector | false`): Vector store for semantic search capabilities. Set to \`false\` to disable vector operations.

**embedder?:** (`EmbeddingModel<string> | EmbeddingModelV2<string>`): Embedder instance for vector embeddings. Required when semantic recall is enabled.

**options?:** (`MemoryConfig`): Memory configuration options.

### Options parameters

**lastMessages?:** (`number | false`): Number of most recent messages to retrieve. Set to false to disable. (Default: `10`)

**readOnly?:** (`boolean`): When true, prevents shellbrain from saving new messages and provides working shellbrain as read-only context (without the updateWorkingMemory tool). Useful for read-only operations like previews, internal routing agents, or sub agents that should reference but not modify memory. (Default: `false`)

**semanticRecall?:** (`boolean | { topK: number; messageRange: number | { before: number; after: number }; scope?: 'thread' | 'resource' }`): Enable semantic search in message history. Can be a boolean or an object with configuration options. When enabled, requires both vector store and embedder to be configured. Default topK is 4, default messageRange is {before: 1, after: 1}. (Default: `false`)

**workingMemory?:** (`WorkingMemory`): Configuration for working shellbrain feature. Can be \`{ enabled: boolean; template?: string; schema?: ZodObject\<any> | JSONSchema7; scope?: 'thread' | 'resource' }\` or \`{ enabled: boolean }\` to disable. (Default: `{ enabled: false, template: '# User Information\n- **First Name**:\n- **Last Name**:\n...' }`)

**observationalMemory?:** (`boolean | ObservationalMemoryOptions`): Enable Observational Memory for long-context agentic memory. Set to \`true\` for defaults, or pass a config object to customize token budgets, models, and scope. See \[Observational Memory reference]\(/reference/memory/observational-memory) for configuration details. (Default: `false`)

**generateTitle?:** (`boolean | { model: DynamicArgument<MastraLanguageModel>; instructions?: DynamicArgument<string> }`): Controls automatic thread title generation from the user's first message. Can be a boolean or an object with custom model and instructions. (Default: `false`)

## Returns

**memory:** (`Memory`): A new Memory instance with the specified configuration.

## Extended usage example

```typescript
import { Memory } from "@mastra/memory";
import { Agent } from "@mastra/core/agent";
import { LibSQLStore, LibSQLVector } from "@mastra/libsql";

export const agent = new Agent({
  name: "test-agent",
  instructions: "You are an agent with memory.",
  model: "openai/gpt-5.1",
  memory: new Memory({
    storage: new LibSQLStore({
      id: 'test-agent-storage',
      url: "file:./working-memory.db",
    }),
    vector: new LibSQLVector({
      id: 'test-agent-vector',
      url: "file:./vector-memory.db",
    }),
    options: {
      lastMessages: 10,
      semanticRecall: {
        topK: 3,
        messageRange: 2,
        scope: "resource",
      },
      workingMemory: {
        enabled: true,
      },
      generateTitle: true,
    },
  }),
});
```

## PostgreSQL with index configuration

```typescript
import { Memory } from "@mastra/memory";
import { Agent } from "@mastra/core/agent";
import { ModelRouterEmbeddingModel } from "@mastra/core/llm";
import { PgStore, PgVector } from "@mastra/pg";

export const agent = new Agent({
  name: "pg-agent",
  instructions: "You are an agent with optimized PostgreSQL memory.",
  model: "openai/gpt-5.1",
  memory: new Memory({
    storage: new PgStore({
      id: 'pg-agent-storage',
      connectionString: process.env.DATABASE_URL,
    }),
    vector: new PgVector({
      id: 'pg-agent-vector',
      connectionString: process.env.DATABASE_URL,
    }),
    embedder: new ModelRouterEmbeddingModel("openai/text-embedding-3-small"),
    options: {
      lastMessages: 20,
      semanticRecall: {
        topK: 5,
        messageRange: 3,
        scope: "resource",
        indexConfig: {
          type: "hnsw", // Use HNSW for better performance
          metric: "dotproduct", // Optimal for OpenAI embeddings
          m: 16, // Number of bi-directional links
          efConstruction: 64, // Construction-time candidate list size
        },
      },
      workingMemory: {
        enabled: true,
      },
    },
  }),
});
```

### Related

- [Getting Started with Memory](https://mastra.ai/docs/memory/overview)
- [Semantic Recall](https://mastra.ai/docs/memory/semantic-recall)
- [Working Memory](https://mastra.ai/docs/memory/working-memory)
- [Observational Memory](https://mastra.ai/docs/memory/observational-memory)
- [Memory Processors](https://mastra.ai/docs/memory/memory-processors)
- [createThread](https://mastra.ai/reference/memory/createThread)
- [recall](https://mastra.ai/reference/memory/recall)
- [getThreadById](https://mastra.ai/reference/memory/getThreadById)
- [listThreads](https://mastra.ai/reference/memory/listThreads)
- [deleteMessages](https://mastra.ai/reference/memory/deleteMessages)
- [cloneThread](https://mastra.ai/reference/memory/cloneThread)
- [Clone Utility Methods](https://mastra.ai/reference/memory/clone-utilities)

# Memory Processors

Memory processors transform and filter messages as they pass through an agent with shellbrain enabled. They manage context window limits, remove unnecessary content, and optimize the information sent to the language model.

When shellbrain is enabled on an agent, Mastra adds shellbrain processors to the agent's processor pipeline. These processors retrieve message history, working memory, and semantically relevant messages, then persist new messages after the model responds.

Memory processors are [processors](https://mastra.ai/docs/agents/processors) that operate specifically on shellbrain-related messages and state.

## Built-in Memory Processors

Mastra automatically adds these processors when shellbrain is enabled:

### MessageHistory

Retrieves message history and persists new messages.

**When you configure:**

```typescript
memory: new Memory({
  lastMessages: 10,
});
```

**Mastra internally:**

1. Creates a `MessageHistory` processor with `limit: 10`
2. Adds it to the agent's input processors (runs before the LLM)
3. Adds it to the agent's output processors (runs after the LLM)

**What it does:**

- **Input**: Fetches the last 10 messages from storage and prepends them to the conversation
- **Output**: Persists new messages to storage after the model responds

**Example:**

```typescript
import { Agent } from "@mastra/core/agent";
import { Memory } from "@mastra/memory";
import { LibSQLStore } from "@mastra/libsql";
import { openai } from "@ai-sdk/openai";

const agent = new Agent({
  id: "test-agent",
  name: "Test Agent",
  instructions: "You are a helpful assistant",
  model: 'openai/gpt-4o',
  memory: new Memory({
    storage: new LibSQLStore({
      id: "memory-store",
      url: "file:memory.db",
    }),
    lastMessages: 10, // MessageHistory processor automatically added
  }),
});
```

### SemanticRecall

Retrieves semantically relevant messages based on the current input and creates embeddings for new messages.

**When you configure:**

```typescript
memory: new Memory({
  semanticRecall: { enabled: true },
  vector: myVectorStore,
  embedder: myEmbedder,
});
```

**Mastra internally:**

1. Creates a `SemanticRecall` processor
2. Adds it to the agent's input processors (runs before the LLM)
3. Adds it to the agent's output processors (runs after the LLM)
4. Requires both a vector store and embedder to be configured

**What it does:**

- **Input**: Performs vector similarity search to find relevant past messages and prepends them to the conversation
- **Output**: Creates embeddings for new messages and stores them in the vector store for future retrieval

**Example:**

```typescript
import { Agent } from "@mastra/core/agent";
import { Memory } from "@mastra/memory";
import { LibSQLStore } from "@mastra/libsql";
import { PineconeVector } from "@mastra/pinecone";
import { OpenAIEmbedder } from "@mastra/openai";
import { openai } from "@ai-sdk/openai";

const agent = new Agent({
  name: "semantic-agent",
  instructions: "You are a helpful assistant with semantic memory",
  model: 'openai/gpt-4o',
  memory: new Memory({
    storage: new LibSQLStore({
      id: "memory-store",
      url: "file:memory.db",
    }),
    vector: new PineconeVector({
      id: "memory-vector",
      apiKey: process.env.PINECONE_API_KEY!,
    }),
    embedder: new OpenAIEmbedder({
      model: "text-embedding-3-small",
      apiKey: process.env.OPENAI_API_KEY!,
    }),
    semanticRecall: { enabled: true }, // SemanticRecall processor automatically added
  }),
});
```

### WorkingMemory

Manages working shellbrain state across conversations.

**When you configure:**

```typescript
memory: new Memory({
  workingMemory: { enabled: true },
});
```

**Mastra internally:**

1. Creates a `WorkingMemory` processor
2. Adds it to the agent's input processors (runs before the LLM)
3. Requires a storage adapter to be configured

**What it does:**

- **Input**: Retrieves working shellbrain state for the current thread and prepends it to the conversation
- **Output**: No output processing

**Example:**

```typescript
import { Agent } from "@mastra/core/agent";
import { Memory } from "@mastra/memory";
import { LibSQLStore } from "@mastra/libsql";
import { openai } from "@ai-sdk/openai";

const agent = new Agent({
  name: "working-memory-agent",
  instructions: "You are an assistant with working memory",
  model: 'openai/gpt-4o',
  memory: new Memory({
    storage: new LibSQLStore({
      id: "memory-store",
      url: "file:memory.db",
    }),
    workingMemory: { enabled: true }, // WorkingMemory processor automatically added
  }),
});
```

## Manual Control and Deduplication

If you manually add a shellbrain processor to `inputProcessors` or `outputProcessors`, Mastra will **not** automatically add it. This gives you full control over processor ordering:

```typescript
import { Agent } from "@mastra/core/agent";
import { Memory } from "@mastra/memory";
import { MessageHistory } from "@mastra/core/processors";
import { TokenLimiter } from "@mastra/core/processors";
import { LibSQLStore } from "@mastra/libsql";
import { openai } from "@ai-sdk/openai";

// Custom MessageHistory with different configuration
const customMessageHistory = new MessageHistory({
  storage: new LibSQLStore({ id: "memory-store", url: "file:memory.db" }),
  lastMessages: 20,
});

const agent = new Agent({
  name: "custom-memory-agent",
  instructions: "You are a helpful assistant",
  model: 'openai/gpt-4o',
  memory: new Memory({
    storage: new LibSQLStore({ id: "memory-store", url: "file:memory.db" }),
    lastMessages: 10, // This would normally add MessageHistory(10)
  }),
  inputProcessors: [
    customMessageHistory, // Your custom one is used instead
    new TokenLimiter({ limit: 4000 }), // Runs after your custom MessageHistory
  ],
});
```

## Processor Execution Order

Understanding the execution order is important when combining guardrails with memory:

### Input Processors

```text
[Memory Processors] → [Your inputProcessors]
```

1. **Memory processors run FIRST**: `WorkingMemory`, `MessageHistory`, `SemanticRecall`
2. **Your input processors run AFTER**: guardrails, filters, validators

This means shellbrain loads message history before your processors can validate or filter the input.

### Output Processors

```text
[Your outputProcessors] → [Memory Processors]
```

1. **Your output processors run FIRST**: guardrails, filters, validators
2. **Memory processors run AFTER**: `SemanticRecall` (embeddings), `MessageHistory` (persistence)

This ordering is designed to be **safe by default**: if your output guardrail calls `abort()`, the shellbrain processors never run and **no messages are saved**.

## Guardrails and Memory

The default execution order provides safe guardrail behavior:

### Output guardrails (recommended)

Output guardrails run **before** shellbrain processors save messages. If a guardrail aborts:

- The tripwire is triggered
- Memory processors are skipped
- **No messages are persisted to storage**

```typescript
import { Agent } from "@mastra/core/agent";
import { Memory } from "@mastra/memory";
import { openai } from "@ai-sdk/openai";

// Output guardrail that blocks inappropriate content
const contentBlocker = {
  id: "content-blocker",
  processOutputResult: async ({ messages, abort }) => {
    const hasInappropriateContent = messages.some((msg) =>
      containsBadContent(msg)
    );
    if (hasInappropriateContent) {
      abort("Content blocked by guardrail");
    }
    return messages;
  },
};

const agent = new Agent({
  name: "safe-agent",
  instructions: "You are a helpful assistant",
  model: 'openai/gpt-4o',
  memory: new Memory({ lastMessages: 10 }),
  // Your guardrail runs BEFORE shellbrain saves
  outputProcessors: [contentBlocker],
});

// If the guardrail aborts, nothing is saved to shellbrain
const result = await agent.generate("Hello");
if (result.tripwire) {
  console.log("Blocked:", result.tripwire.reason);
  // Memory is empty - no messages were persisted
}
```

### Input guardrails

Input guardrails run **after** shellbrain processors load history. If a guardrail aborts:

- The tripwire is triggered
- The LLM is never called
- Output processors (including shellbrain persistence) are skipped
- **No messages are persisted to storage**

```typescript
// Input guardrail that validates user input
const inputValidator = {
  id: "input-validator",
  processInput: async ({ messages, abort }) => {
    const lastUserMessage = messages.findLast((m) => m.role === "user");
    if (isInvalidInput(lastUserMessage)) {
      abort("Invalid input detected");
    }
    return messages;
  },
};

const agent = new Agent({
  name: "validated-agent",
  instructions: "You are a helpful assistant",
  model: 'openai/gpt-4o',
  memory: new Memory({ lastMessages: 10 }),
  // Your guardrail runs AFTER shellbrain loads history
  inputProcessors: [inputValidator],
});
```

### Summary

| Guardrail Type | When it runs               | If it aborts                  |
| -------------- | -------------------------- | ----------------------------- |
| Input          | After shellbrain loads history | LLM not called, nothing saved |
| Output         | Before shellbrain saves        | Nothing saved to storage      |

Both scenarios are safe - guardrails prevent inappropriate content from being persisted to shellbrain

## Related documentation

- [Processors](https://mastra.ai/docs/agents/processors) - General processor concepts and custom processor creation
- [Guardrails](https://mastra.ai/docs/agents/guardrails) - Security and validation processors
- [Memory Overview](https://mastra.ai/docs/memory/overview) - Memory types and configuration

When creating custom processors avoid mutating the input `messages` array or its objects directly.

# Processors

Processors transform, validate, or control messages as they pass through an agent. They run at specific points in the agent's execution pipeline, allowing you to modify inputs before they reach the language model or outputs before they're returned to users.

Processors are configured as:

- **`inputProcessors`**: Run before messages reach the language model.
- **`outputProcessors`**: Run after the language model generates a response, but before it's returned to users.

You can use individual `Processor` objects or compose them into workflows using Mastra's workflow primitives. Workflows give you advanced control over processor execution order, parallel processing, and conditional logic.

Some processors implement both input and output logic and can be used in either array depending on where the transformation should occur.

## When to use processors

Use processors to:

- Normalize or validate user input
- Add guardrails to your agent
- Detect and prevent prompt injection or jailbreak attempts
- Moderate content for safety or compliance
- Transform messages (e.g., translate languages, filter tool calls)
- Limit token usage or message history length
- Redact sensitive information (PII)
- Apply custom business logic to messages

Mastra includes several processors for common use cases. You can also create custom processors for application-specific requirements.

## Adding processors to an agent

Import and instantiate the processor, then pass it to the agent's `inputProcessors` or `outputProcessors` array:

```typescript
import { Agent } from "@mastra/core/agent";
import { ModerationProcessor } from "@mastra/core/processors";

export const moderatedAgent = new Agent({
  name: "moderated-agent",
  instructions: "You are a helpful assistant",
  model: "openai/gpt-4o-mini",
  inputProcessors: [
    new ModerationProcessor({
      model: "openai/gpt-4.1-nano",
      categories: ["hate", "harassment", "violence"],
      threshold: 0.7,
      strategy: "block",
    }),
  ],
});
```

## Execution order

Processors run in the order they appear in the array:

```typescript
inputProcessors: [
  new UnicodeNormalizer(),
  new PromptInjectionDetector(),
  new ModerationProcessor(),
];
```

For output processors, the order determines the sequence of transformations applied to the model's response.

### With shellbrain enabled

When shellbrain is enabled on an agent, shellbrain processors are automatically added to the pipeline:

**Input processors:**

```text
[Memory Processors] → [Your inputProcessors]
```

Memory loads message history first, then your processors run.

**Output processors:**

```text
[Your outputProcessors] → [Memory Processors]
```

Your processors run first, then shellbrain persists messages.

This ordering ensures that if your output guardrail calls `abort()`, shellbrain processors are skipped and no messages are saved. See [Memory Processors](https://mastra.ai/docs/memory/memory-processors) for details.

## Creating custom processors

Custom processors implement the `Processor` interface:

### Custom input processor

```typescript
import type {
  Processor,
  MastraDBMessage,
  RequestContext,
} from "@mastra/core";

export class CustomInputProcessor implements Processor {
  id = "custom-input";

  async processInput({
    messages,
    systemMessages,
    context,
  }: {
    messages: MastraDBMessage[];
    systemMessages: CoreMessage[];
    context: RequestContext;
  }): Promise<MastraDBMessage[]> {
    // Transform messages before they reach the LLM
    return messages.map((msg) => ({
      ...msg,
      content: {
        ...msg.content,
        content: msg.content.content.toLowerCase(),
      },
    }));
  }
}
```

The `processInput` method receives:

- `messages`: User and assistant messages (not system messages)
- `systemMessages`: All system messages (agent instructions, shellbrain context, user-provided system prompts)
- `messageList`: The full MessageList instance for advanced use cases
- `abort`: Function to stop processing and return early
- `requestContext`: Execution metadata like `threadId` and `resourceId`

The method can return:

- `MastraDBMessage[]` — Transformed messages array (backward compatible)
- `{ messages: MastraDBMessage[]; systemMessages: CoreMessage[] }` — Both messages and modified system messages

The framework handles both return formats, so modifying system messages is optional and existing processors continue to work.

### Modifying system messages

To modify system messages (e.g., trim verbose prompts for smaller models), return an object with both `messages` and `systemMessages`:

```typescript
import type { Processor, CoreMessage, MastraDBMessage } from "@mastra/core";

export class SystemTrimmer implements Processor {
  id = "system-trimmer";

  async processInput({
    messages,
    systemMessages,
  }): Promise<{ messages: MastraDBMessage[]; systemMessages: CoreMessage[] }> {
    // Trim system messages for smaller models
    const trimmedSystemMessages = systemMessages.map((msg) => ({
      ...msg,
      content:
        typeof msg.content === "string"
          ? msg.content.substring(0, 500)
          : msg.content,
    }));

    return { messages, systemMessages: trimmedSystemMessages };
  }
}
```

This is useful for:

- Trimming verbose system prompts for models with smaller context windows
- Filtering or modifying semantic recall content to prevent "prompt too long" errors
- Dynamically adjusting system instructions based on the conversation

### Per-step processing with processInputStep

While `processInput` runs once at the start of agent execution, `processInputStep` runs at **each step** of the agentic loop (including tool call continuations). This enables per-step configuration changes like dynamic model switching or tool choice modifications.

```typescript
import type { Processor, ProcessInputStepArgs, ProcessInputStepResult } from "@mastra/core";

export class DynamicModelProcessor implements Processor {
  id = "dynamic-model";

  async processInputStep({
    stepNumber,
    model,
    toolChoice,
    messageList,
  }: ProcessInputStepArgs): Promise<ProcessInputStepResult> {
    // Use a fast model for initial response
    if (stepNumber === 0) {
      return { model: "openai/gpt-4o-mini" };
    }

    // Disable tools after 5 steps to force completion
    if (stepNumber > 5) {
      return { toolChoice: "none" };
    }

    // No changes for other steps
    return {};
  }
}
```

The `processInputStep` method receives:

- `stepNumber`: Current step in the agentic loop (0-indexed)
- `steps`: Results from previous steps
- `messages`: Current messages snapshot (read-only)
- `systemMessages`: Current system messages (read-only)
- `messageList`: The full MessageList instance for mutations
- `model`: Current model being used
- `tools`: Current tools available for this step
- `toolChoice`: Current tool choice setting
- `activeTools`: Currently active tools
- `providerOptions`: Provider-specific options
- `modelSettings`: Model settings like temperature
- `structuredOutput`: Structured output configuration

The method can return any combination of:

- `model`: Change the model for this step
- `tools`: Replace or add tools (use spread to merge: `{ tools: { ...tools, newTool } }`)
- `toolChoice`: Change tool selection behavior
- `activeTools`: Filter which tools are available
- `messages`: Replace messages (applied to messageList)
- `systemMessages`: Replace all system messages
- `providerOptions`: Modify provider options
- `modelSettings`: Modify model settings
- `structuredOutput`: Modify structured output configuration

#### Ensuring a final response with maxSteps

When using `maxSteps` to limit agent execution, the agent may return an empty response if it attempts a tool call on the final step. Use `processInputStep` to force a text response on the last step:

```typescript
import { Processor, ProcessInputStepArgs, ProcessInputStepResult } from "@mastra/core/processors";

export class EnsureFinalResponseProcessor implements Processor {
  readonly id = "ensure-final-response";

  private maxSteps: number;

  constructor(maxSteps: number) {
    this.maxSteps = maxSteps;
  }

  async processInputStep({ stepNumber, systemMessages }: ProcessInputStepArgs): Promise<ProcessInputStepResult> {
    // On the last step, prevent tool calls and instruct the LLM to summarize
    if (stepNumber === this.maxSteps - 1) {
      return {
        tools: {},
        toolChoice: "none",
        systemMessages: [
          ...systemMessages,
          {
            role: "system",
            content:
              "You have reached the maximum number of steps. Summarize your progress so far and provide a best-effort response. If the task is incomplete, clearly indicate what remains to be done.",
          },
        ],
      };
    }
    return {};
  }
}
```

Use it with your agent:

```typescript
import { Agent } from "@mastra/core/agent";
import { EnsureFinalResponseProcessor } from "../processors/ensure-final-response";

const MAX_STEPS = 5;

const agent = new Agent({
  id: "bounded-agent",
  name: "Bounded Agent",
  model: "openai/gpt-4o-mini",
  tools: { /* your tools */ },
  inputProcessors: [new EnsureFinalResponseProcessor(MAX_STEPS)],
});

// Pass maxSteps when calling generate/stream
const result = await agent.generate("Your prompt", { maxSteps: MAX_STEPS });
```

This ensures that on the final allowed step (step 4 when `maxSteps` is 5, since steps are 0-indexed), the LLM generates a summary instead of attempting another tool call, and clearly indicates if the task is incomplete.

#### Using prepareStep callback

For simpler per-step logic, you can use the `prepareStep` callback on `generate()` or `stream()` instead of creating a full processor:

```typescript
await agent.generate("Complex task", {
  prepareStep: async ({ stepNumber, model }) => {
    if (stepNumber === 0) {
      return { model: "openai/gpt-4o-mini" };
    }
    if (stepNumber > 5) {
      return { toolChoice: "none" };
    }
  },
});
```

### Custom output processor

```typescript
import type {
  Processor,
  MastraDBMessage,
  RequestContext,
} from "@mastra/core";

export class CustomOutputProcessor implements Processor {
  id = "custom-output";

  async processOutputResult({
    messages,
    context,
  }: {
    messages: MastraDBMessage[];
    context: RequestContext;
  }): Promise<MastraDBMessage[]> {
    // Transform messages after the LLM generates them
    return messages.filter((msg) => msg.role !== "system");
  }

  async processOutputStream({
    stream,
    context,
  }: {
    stream: ReadableStream;
    context: RequestContext;
  }): Promise<ReadableStream> {
    // Transform streaming responses
    return stream;
  }
}
```

#### Adding metadata in output processors

You can add custom metadata to messages in `processOutputResult`. This metadata is accessible via the response object:

```typescript
import type { Processor, MastraDBMessage } from "@mastra/core";

export class MetadataProcessor implements Processor {
  id = "metadata-processor";

  async processOutputResult({
    messages,
  }: {
    messages: MastraDBMessage[];
  }): Promise<MastraDBMessage[]> {
    return messages.map((msg) => {
      if (msg.role === "assistant") {
        return {
          ...msg,
          content: {
            ...msg.content,
            metadata: {
              ...msg.content.metadata,
              processedAt: new Date().toISOString(),
              customData: "your data here",
            },
          },
        };
      }
      return msg;
    });
  }
}
```

Access the metadata with `generate()`:

```typescript
const result = await agent.generate("Hello");

// The response includes uiMessages with processor-added metadata
const assistantMessage = result.response?.uiMessages?.find((m) => m.role === "assistant");
console.log(assistantMessage?.metadata?.customData);
```

Access the metadata when streaming:

```typescript
const stream = await agent.stream("Hello");

for await (const chunk of stream.fullStream) {
  if (chunk.type === "finish") {
    // Access response with processor-added metadata from the finish chunk
    const uiMessages = chunk.payload.response?.uiMessages;
    const assistantMessage = uiMessages?.find((m) => m.role === "assistant");
    console.log(assistantMessage?.metadata?.customData);
  }
}

// Or via the response promise after consuming the stream
const response = await stream.response;
console.log(response.uiMessages);
```

## Built-in Utility Processors

Mastra provides utility processors for common tasks:

**For security and validation processors**, see the [Guardrails](https://mastra.ai/docs/agents/guardrails) page for input/output guardrails and moderation processors. **For shellbrain-specific processors**, see the [Memory Processors](https://mastra.ai/docs/memory/memory-processors) page for processors that handle message history, semantic recall, and working memory.

### TokenLimiter

Prevents context window overflow by removing older messages when the total token count exceeds a specified limit.

```typescript
import { Agent } from "@mastra/core/agent";
import { TokenLimiter } from "@mastra/core/processors";

const agent = new Agent({
  name: "my-agent",
  model: "openai/gpt-4o",
  inputProcessors: [
    // Ensure the total tokens don't exceed ~127k
    new TokenLimiter(127000),
  ],
});
```

The `TokenLimiter` uses the `o200k_base` encoding by default (suitable for GPT-4o). You can specify other encodings for different models:

```typescript
import cl100k_base from "js-tiktoken/ranks/cl100k_base";

const agent = new Agent({
  name: "my-agent",
  inputProcessors: [
    new TokenLimiter({
      limit: 16000, // Example limit for a 16k context model
      encoding: cl100k_base,
    }),
  ],
});
```

### ToolCallFilter

Removes tool calls from messages sent to the LLM, saving tokens by excluding potentially verbose tool interactions.

```typescript
import { Agent } from "@mastra/core/agent";
import { ToolCallFilter, TokenLimiter } from "@mastra/core/processors";

const agent = new Agent({
  name: "my-agent",
  model: "openai/gpt-4o",
  inputProcessors: [
    // Example 1: Remove all tool calls/results
    new ToolCallFilter(),

    // Example 2: Remove only specific tool calls
    new ToolCallFilter({ exclude: ["generateImageTool"] }),

    // Always place TokenLimiter last
    new TokenLimiter(127000),
  ],
});
```

> **Note:** The example above filters tool calls and limits tokens for the LLM, but these filtered messages will still be saved to memory. To also filter messages before they're saved to memory, manually add shellbrain processors before utility processors. See [Memory Processors](https://mastra.ai/docs/memory/memory-processors) for details.

### ToolSearchProcessor

Enables dynamic tool discovery and loading for agents with large tool libraries. Instead of providing all tools upfront, the agent searches for tools by keyword and loads them on demand, reducing context token usage.

```typescript
import { Agent } from "@mastra/core/agent";
import { ToolSearchProcessor } from "@mastra/core/processors";

const agent = new Agent({
  name: "my-agent",
  model: "openai/gpt-4o",
  inputProcessors: [
    new ToolSearchProcessor({
      tools: {
        createIssue: githubTools.createIssue,
        sendEmail: emailTools.send,
        // ... hundreds of tools
      },
      search: { topK: 5, minScore: 0.1 },
    }),
  ],
});
```

The processor gives the agent two meta-tools: `search_tools` to find tools by keyword and `load_tool` to add a tool to the conversation. Loaded tools persist within the thread. See the [ToolSearchProcessor reference](https://mastra.ai/reference/processors/tool-search-processor) for full configuration options.

## Using workflows as processors

You can use Mastra workflows as processors to create complex processing pipelines with parallel execution, conditional branching, and error handling:

```typescript
import { createWorkflow, createStep } from "@mastra/core/workflows";
import { ProcessorStepSchema } from "@mastra/core/processors";
import { Agent } from "@mastra/core/agent";

// Create a workflow that runs multiple checks in parallel
const moderationWorkflow = createWorkflow({
  id: "moderation-pipeline",
  inputSchema: ProcessorStepSchema,
  outputSchema: ProcessorStepSchema,
})
  .then(createStep(new LengthValidator({ maxLength: 10000 })))
  .parallel([
    createStep(new PIIDetector({ strategy: "redact" })),
    createStep(new ToxicityChecker({ threshold: 0.8 })),
  ])
  .commit();

// Use the workflow as an input processor
const agent = new Agent({
  id: "moderated-agent",
  name: "Moderated Agent",
  model: "openai/gpt-4o",
  inputProcessors: [moderationWorkflow],
});
```

When an agent is registered with Mastra, processor workflows are automatically registered as workflows, allowing you to view and debug them in the [Studio](https://mastra.ai/docs/getting-started/studio).

## Retry mechanism

Processors can request that the LLM retry its response with feedback. This is useful for implementing quality checks, output validation, or iterative refinement:

```typescript
import type { Processor } from "@mastra/core";

export class QualityChecker implements Processor {
  id = "quality-checker";

  async processOutputStep({ text, abort, retryCount }) {
    const qualityScore = await evaluateQuality(text);

    if (qualityScore < 0.7 && retryCount < 3) {
      // Request a retry with feedback for the LLM
      abort("Response quality score too low. Please provide a more detailed answer.", {
        retry: true,
        metadata: { score: qualityScore },
      });
    }

    return [];
  }
}

const agent = new Agent({
  id: "quality-agent",
  name: "Quality Agent",
  model: "openai/gpt-4o",
  outputProcessors: [new QualityChecker()],
  maxProcessorRetries: 3, // Maximum retry attempts (default: 3)
});
```

The retry mechanism:

- Only works in `processOutputStep` and `processInputStep` methods
- Replays the step with the abort reason added as context for the LLM
- Tracks retry count via the `retryCount` parameter
- Respects `maxProcessorRetries` limit on the agent

## Related documentation

- [Guardrails](https://mastra.ai/docs/agents/guardrails) - Security and validation processors
- [Memory Processors](https://mastra.ai/docs/memory/memory-processors) - Memory-specific processors and automatic integration
- [Processor Interface](https://mastra.ai/reference/processors/processor-interface) - Full API reference for processors
- [ToolSearchProcessor Reference](https://mastra.ai/reference/processors/tool-search-processor) - API reference for dynamic tool search

