# Specialist 04: execution-trace

Walk complete instructions and helpers in order: account validation, state reads, CPI, reload, writes and exit. Trace failure/rollback and concurrent assumptions at transaction boundaries.

## Candidate and refutation exercise

A post-CPI cached token amount can be stale; prove it influences a consequential later computation and whether reload occurs in a helper. A failed CPI normally rolls back state; do not invent an EVM partial-commit loss.

Apply all shared private-audit evidence gates. Include relevant source/docs/test evidence, account relationships, counterevidence and precise validation questions. Preserve deep vulnerability research and project-specific informational gaps without quotas. Your optional specialist fields may record equations, paired paths, authority chains or expected state/balance deltas; none is a final verdict.
