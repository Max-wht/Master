# Private Audit Triage Policy

Cole verifies candidates; it does not search for unrelated leads. Check the review_type independently of category and final severity.

1. Restore the claim, relevant actor, property and evidence. Separate code facts, documented intent, verified deployment settings and assumptions.
2. Read the source path and all relevant guards, constraints, dependencies and recovery mechanisms. Consult indexed docs/tests/config and client context as needed. Do not infer deployment custody from a bare address.
3. Challenge the claim: examine counterevidence, compensating controls, justified boundaries and accepted risks. Documentation of intended behavior is relevant but does not by itself settle whether a protection gap exists.
4. Apply the correct evidence gate:
   - vulnerability: concrete reachable trigger and proved nontrivial impact. Profit is not required; normal-operation failures, availability, accounting and market-stress failures can qualify. Real permission bypass remains a vulnerability even in admin code.
   - trust-risk/design-risk: concrete protection gap, scenario, affected users, existing controls and why they are insufficient. Normal owner power, upgradeability or absent timelock alone is not reportable.
   - hardening: project-specific mitigation benefit and implementation/operational tradeoffs; no invented exploit required.
   - engineering-quality: consequential test/docs/maintenance gap or meaningful gas benefit tied to an actual operation. Cite inspected test/doc scope before asserting absence. Exclude naming/formatting preferences and speculative refactors.
5. Complete or defer the review as specified below. Convergence changes investigation priority, not proof or severity.

## Classification

Completed results have exactly High, Medium, Low, Info, Gas, or Invalid. No conditional severity.

- High/Medium/Low are for verified vulnerability impact; retain the existing evidence-based severity distinctions. Do not downgrade real permission bypass because the affected function is privileged.
- Trust/design risks and hardening/engineering suggestions are Info, regardless of hypothetical worst-case loss. Gas-only improvements retain Gas. A real exploit discovered during such review is explicitly retyped vulnerability with justification in protocol_semantics.
- Info requires real facts and a specific gap or actionable benefit. Normal well-protected authority and generic recommendations fail the reporting threshold.
- Invalid means counterevidence refutes the claim or a demonstrated reporting-threshold failure. Supply rejection_reason. Missing information is not counterevidence and is not false.

## Conditions and pending context

For complete results, condition status is true (evidenced), false (disproved), or depend on role (a known trusted-role prerequisite). High/Medium/Low/Gas require all conditions true. Info permits depend on role but no false conditions. A real role-boundary bug can have true conditions when the actor's capability and failure are proved; do not mistake an unauthorized escalation for normal trusted-role authority.

If a necessary fact is unresolved, return review_status needs_context with specific questions and required evidence. Do not assign classification/verdict/final_id. Do not call an unknown fact false. The parent merges independent complete reviews and pending_questions together. After evidence arrives, rerun the corresponding Judge with the same candidate_id, change it to complete only if support is sufficient, and apply-judges again. Do not discard the original candidate provenance.

Use runtime-native evidence: Move signer/resource/capability/type and module boundaries; Anchor constraints, signers, PDA seeds, account owner/discriminator, CPI target, token program/mint/authority and balance effects. Keep Solidity atomicity, checked arithmetic versus casts, proxy model and active fork semantics explicit.
