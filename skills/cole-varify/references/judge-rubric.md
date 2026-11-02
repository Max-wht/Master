# Private Audit Judge Rubric

Review exactly one candidate. Neither assume its truth nor defend its initial label. Use triage-policy.md as the binding classification policy.

- Restore the scenario, actor, affected guarantee, claim type and source evidence.
- Verify execution/reachability for vulnerability claims, or the concrete gap/applicability for informational reviews. Trace guards and compensating controls; ordinary trusted authority is background unless a protection gap is demonstrated.
- Read relevant source, docs, configuration and tests. Label observed code, documented intent, verified deployment and assumptions separately. A client statement is not an on-chain verification.
- Identify counterevidence and reasonable design explanations. For accepted risks, assess whether the specific claimed protection gap still warrants disclosure; do not mechanically suppress it or report authority alone.
- For recommendations, explain benefits and costs, including latency, emergency response, compatibility and maintenance. Missing tests must identify inspected tests and the untested consequential scenario.
- Use complete only when classification can be justified. For Invalid, explain the counterevidence or unmet reporting criterion. Missing proof requires needs_context with precise questions and requested evidence, never forced false conditions.
- Preserve deep impact analysis for vulnerabilities, including non-profitable normal-operation/market-stress paths; distinguish these from ordinary intended investment loss.
- Write both configured output files using report-format.md. Source-backed Info does not require a PoC; any execution claim needing a test follows poc-policy.md and the preflight state.
