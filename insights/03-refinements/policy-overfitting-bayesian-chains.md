# Policy Note: Overfitting, Bayesian Framing, and Chain Types

Captured from the 2026-02-18 discovery refinement.

## 1) Policy for stale-shellbrain overfitting

Core policy:
- **Memories are optional utility, not truth.**
- **Current code/workspace observations are the instantaneous truth source.**

Operational behavior:
- Retrieve memories as candidate tools, not commands.
- Validate candidates against what the agent sees now.
- If conflict exists, trust current code and treat shellbrain as stale-or-context-limited.
- Record what changed and why in update memories after the session.

## 2) Global utility and Bayesian commonality

Working position:
- Global utility can exist as a weak prior.
- It should be computed after the fact from contextual observations, not treated as the primary signal.

Emerging idea:
- Utility and truth both look like beliefs updated over evidence.
- This suggests a possible Bayesian formalization:
  - Utility prior -> updated by problem-specific outcomes.
  - Truth prior in `[0,1]` -> updated by contradiction/support evidence.
- Formal Bayesian machinery is optional; the conceptual alignment is the key discovery.

## 3) Chain realization: implicit vs explicit association

Two chain classes are now recognized:
- Implicit association chain: semantic/vector similarity expansion.
- Explicit association chain: mandatory deterministic traversal via formal links (for example, shellbrain -> its updates).

Key insight:
- Update memories are not just "more similar neighbors."
- Update memories are a special linked class that should always be traversed when their base shellbrain is retrieved.
