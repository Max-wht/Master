# PoC Policy

Create PoCs only after preflight succeeds and source triage identifies a candidate worth testing.

Preflight succeeds for PoC purposes only when `preflight.json` has `status: "passed"`. If it has `status: "skipped-local-build"`, stay in logic-only mode and do not create PoCs or run tests.

Directory:

```text
test/MasterWuCole/
```

Naming:

```text
COLE-001.t.sol
COLE-002.t.sol
```

Foundry command:

```bash
forge test --match-path test/MasterWuCole/COLE-001.t.sol -vvv
```

Rules:

- Do not modify target contracts.
- Keep each PoC minimal and candidate-specific.
- A PoC may prove exploitability or prove that the candidate is blocked.
- Prefer local deterministic tests over fork tests for v1 unless a fork is required for the claim.
- Record the exact test command and result in `results.json`.

Skip-local-build mode:

- Use `poc.path: ""`.
- Use `poc.test_command: ""`.
- Use `poc.test_result: "not-run"` or `"blocked"`.
- Use `poc.notes: "Skipped because --skip-local-build was used."`.
- Mark execution-dependent candidates as `needs-poc`, not `confirmed`.
