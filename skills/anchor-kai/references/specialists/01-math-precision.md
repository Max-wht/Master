# Specialist 01: math-precision

Trace u64/u128/i64 operations, casts, checked/saturating behavior, Cargo overflow profiles, fixed-point scale/decimals, rounding and slot/time conversion across asset paths.

## Candidate and refutation exercise

Compare deposit/withdraw round trips and boundary amounts. A checked_add that rejects overflow is counterevidence to wraparound; saturating clamps may still violate accounting. Quantify dust accumulation/impact before recommending wider math.

Apply all shared private-audit evidence gates. Include relevant source/docs/test evidence, account relationships, counterevidence and precise validation questions. Preserve deep vulnerability research and project-specific informational gaps without quotas. Your optional specialist fields may record equations, paired paths, authority chains or expected state/balance deltas; none is a final verdict.
