# Candidate Evidence Gates

Kai outputs hypotheses and validation leads, never confirmed findings or severity. Confidence measures support for the stated claim, not impact or bounty eligibility.

## 1. Establish the claim and review type

Use vulnerability, trust-risk, design-risk, hardening, or engineering-quality independently of the technical category. Identify the property, concrete gap, or improvement opportunity. An actual permission bypass is a vulnerability, not an informational governance concern.

## 2. Check evidence and applicability

Trace the relevant callers, guards, state changes, and compensating controls. Read docs/tests/config where needed. Separate verified facts from assumptions. A contradictory guard defeats the claimed path only if it actually interrupts the relevant step. Speculative deployment choices do not prove safety or danger.

- Vulnerability: show a reachable trigger and concrete nontrivial harm, including loss, stuck assets, availability, unauthorized control, or broken accounting. Self-harm or ordinary intended investment loss alone is insufficient.
- Trust/design risk: show the specific capability or mechanism, affected users/operations, failure scenario, existing protections, and why the gap matters. Normal authority alone is insufficient; no fabricated unprivileged attacker is needed.
- Hardening: show a project-specific failure scenario mitigated by the change, existing protection, expected benefit, and costs. Do not claim an exploit has been established.
- Engineering quality: demonstrate a consequential test/documentation/maintenance gap or meaningful gas improvement in an actual operation. Identify what was inspected and a concrete fix or test. No formatting or naming preferences.

## 3. Challenge the claim

Actively look for enforced invariants, inherited checks, recovery paths, justified trust boundaries, supported-token restrictions, and tests contradicting the claim. Intended design is evidence to assess, not automatic rejection or acceptance. A refuted claim is a rejected lead; an unresolved fact is a context question. Do not promote a lead merely because other agents agree.

## 4. State support and next validation

Use high confidence for complete source-backed reasoning with established preconditions; medium for concrete evidence with limited unverified assumptions; low for a specific unresolved trail. Explain missing evidence directly. Quantify numerical/economic claims with reachable values; label illustrative inputs as assumptions. Recommendations are not evidence of a bug.

## Market security

Preserve the market-security branch of economic-security. Start with truthful prices and normal user/keeper behavior. Trace price/time sequence, configuration, updates, liquidation, liquidity, and recovery. A reachable market move and ordinary protocol transition may trigger material mechanism-caused harm without an attacker or profitable trigger. Separate this from normal investment loss or intended risk allocation. Unverified market inputs remain explicit validation requirements.

## Patterns are questions, not verdicts

SafeERC20, nonReentrant, two-step transfers, minimum-liquidity burns, and protocol-favoring rounding do not establish whole-system safety. Verify coverage and semantics. Explicit Solidity narrowing integer casts truncate; checked arithmetic does not make casts safe. Reverts normally roll back transaction state; partial effects require evidence of caught failures, separate transactions, or externally observable intermediate state. Account for compiler, runtime, fork, and deployment semantics before applying historical exploit patterns.
