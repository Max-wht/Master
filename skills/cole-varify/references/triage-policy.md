# Triage Policy

Cole validates hypotheses. It does not search for more leads.

For every candidate, answer these in order:

1. **Trigger:** Which externally callable function or transaction sequence starts the path?
2. **Actor:** Can an ordinary user trigger it, or does it require owner/admin/governance/keeper permissions?
3. **Guard:** Which modifiers, require checks, allowlists, or state preconditions block or allow the path?
4. **State/value effect:** What state, balance, price, accounting, permission, or message effect changes?
5. **Impact:** Can the effect produce user loss, protocol loss, insolvency, stuck funds, unauthorized control, broken mint/burn accounting, griefing, UX degradation, or gas-only waste?
6. **Design boundary:** Is this behavior documented/intended, a governance choice, a configuration risk, or a code-level bug?

Apply these questions using runtime-native evidence. For Move, check signer/resource/capability ownership, type identity, abort/resource state, and coin/object movement. For Anchor, check account constraints, signer bit, PDA seeds/bump, owner/discriminator, token program/mint/token-account ownership, CPI targets, and lamport/token deltas.

Use only these final classifications:

- `High`
- `Medium`
- `Low`
- `Info`
- `Gas`
- `Invalid`

Rules:

- `High`, `Medium`, and `Low` require source evidence, reachable attack path, protocol semantic mismatch, and proved non-gas impact.
- `Info` is for real code/design facts that are not bounty-grade security impact.
- `Gas` is for gas-only findings.
- `Invalid` is for false conditions, unreachable paths, intended design behavior, normal trusted-role authority, or unclosed impact.
- Do not output conditional severity or a missing-proof category. If exact classification is impossible from current evidence, ask for the missing code/config/docs/PoC context and do not merge the Judge result.
- Required condition status must be exactly `true`, `false`, or `depend on role`.
- `High`, `Medium`, `Low`, and `Gas` require every listed required condition to be `true`.
- `Info` may include `depend on role` for real trusted-role or design-risk notes, but cannot include `false`.
- `Invalid` requires at least one required condition to be `false` or `depend on role`.
