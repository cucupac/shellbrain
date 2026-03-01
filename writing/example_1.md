# Hold Off on Helper Contracts

**Decision: use direct concurrent RPC reads over helper smart contracts for now.**

---

## Why not helper contracts

**No guaranteed benefit.**
The core bet helper contracts make is that *reducing RPC envelope count saves more time than it costs.*

**Transport is already free.**
The indexer and node are co-located. The envelopes we'd be eliminating cost almost nothing.

**The contract serializes work.**
Inside a single `eth_call`, the helper runs every read *sequentially*, then assembles and ABI-encodes the result. That overhead doesn't disappear — it moves onchain.

**Direct calls can parallelize. Helper calls can't.**
With batching and bounded concurrency, direct reads let the node schedule work across workers. Smart contracts serialize it inside one EVM context.

---

## Wait for benchmarks

**Revisit only if target-hardware benchmarks show a clear win.**
We don't have the target machine yet. Committing now means deployment and maintenance complexity with *zero validated upside.*

