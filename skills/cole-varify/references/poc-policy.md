# PoC Policy

Create PoCs only after preflight succeeds and source triage identifies a candidate worth testing.

Preflight succeeds for PoC purposes only when `preflight.json` has `status: "passed"`. If it has `status: "skipped-local-build"`, stay in logic-only mode and do not create PoCs or run tests.

Directories:

```text
Solidity: test/MasterWuCole/
Move: tests/MasterWuCole/
Anchor: tests/masterwu/
```

Temporary candidate names before Judge merge:

```text
Solidity: finding-001.t.sol
Move: finding_001.move
Anchor: finding-001.ts
```

Final names after Judge classification:

```text
Solidity: h-1.t.sol, m-1.t.sol, l-1.t.sol, i-1.t.sol, g-1.t.sol
Move: h_1.move, m_1.move, l_1.move, i_1.move, g_1.move
Anchor: h-1.ts, m-1.ts, l-1.ts, i-1.ts, g-1.ts
```

Invalid findings should not receive new PoCs. If an invalidation PoC exists, keep it referenced as evidence but do not present it as an exploit PoC.

Example commands:

```bash
forge test --match-path test/MasterWuCole/h-1.t.sol -vvv
sui move test --filter h_1
aptos move test --filter h_1
anchor test -- --grep h-1
```

Rules:

- Do not modify target contracts.
- Do not use old finding prefixes in filenames, paths, test filters, or report text.
- For Move, do not modify target modules; add test-only modules under `tests/MasterWuCole/`.
- For Anchor, prefer the existing test harness and add focused tests under `tests/masterwu/`; validate account constraints, PDA seeds, token program/mint/account ownership, CPI, and lamport/token deltas.
- Keep each PoC minimal and candidate-specific.
- A PoC may prove exploitability or prove that the candidate is invalid.
- Prefer local deterministic tests over fork tests for v1 unless a fork is required for the claim.
- Record the exact test command and result in `judge.json`.

Skip-local-build mode:

- Use `poc.path: ""`.
- Use `poc.test_command: ""`.
- Use `poc.test_result: "not-run"` or `"blocked"`.
- Use `poc.notes: "Skipped because --skip-local-build was used."`.
- Do not classify an execution-dependent issue as `High`, `Medium`, or `Low` without exact evidence.
