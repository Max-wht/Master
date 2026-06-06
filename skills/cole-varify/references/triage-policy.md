# Triage Policy

Cole validates hypotheses. It does not search for more leads.

For every candidate, answer these in order:

1. **Trigger:** Which externally callable function or transaction sequence starts the path?
2. **Actor:** Can an ordinary user trigger it, or does it require owner/admin/governance/keeper permissions?
3. **Guard:** Which modifiers, require checks, allowlists, or state preconditions block or allow the path?
4. **State/value effect:** What state, balance, price, accounting, or permission effect changes?
5. **Impact:** Can the effect produce user loss, protocol loss, insolvency, stuck funds, unauthorized control, or another concrete harm?
6. **Design boundary:** Is this behavior documented/intended, a governance choice, a configuration risk, or a code-level bug?

Use these labels exactly:

- `verification_status`: `confirmed`, `rejected`, `needs-poc`, `blocked-build`, `blocked-missing-context`.
- `reachability`: `ordinary-user-reachable`, `trusted-role-only`, `governance-only`, `configuration-dependent`, `unreachable`.
- `nature`: `real-bug`, `design-choice`, `configuration-risk`, `trusted-role-risk`, `false-positive`.

Rules:

- `confirmed` requires source evidence plus a concrete trigger and impact path.
- `ordinary-user-reachable` requires no trusted role in the exploit path.
- Trusted-role, governance-only, and configuration-dependent issues are not ordinary-user bugs unless the harmful state can be reached without trusting that role.
- If the path may be real but needs execution proof, use `needs-poc`.
- If missing docs, deployment state, or external config prevents a fair decision, use `blocked-missing-context`.

