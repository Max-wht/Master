# On-Demand PoC Policy

Source review is the default. Only create/run a candidate-specific PoC after preflight status passed AND test_harness.available is true. Missing toolchain, failed build or absent configured tests blocks execution, while source-sufficient reviews continue. Do not install toolchains or create a local-validator/LiteSVM/Mollusk sandbox.

Reuse the target's actual existing configuration:
- Anchor TS/JS tests with Anchor.toml scripts.test: use the configured runner and its supported test filter.
- Existing JS LiteSVM/project tests: use package.json scripts.test and its supported selection mechanism.
- Rust LiteSVM/Mollusk/program-test/integration tests: use the applicable Cargo package/test target and existing fixtures. Dependency names alone are not proof that a runnable harness exists.
- Discovery records readiness, not a promise every dependency/service is installed. If the selected runner fails, record failed or blocked with exact evidence; never fabricate success.

Add focused tests in the existing test layout, e.g. tests/masterwu/finding-001.ts or an existing Rust test module. Do not alter target program code. Never automatically deploy to the Anchor provider cluster; review the configured test command and ensure execution is local before running it.

poc records path, test_command, test_result (not-run/passed/failed/blocked), notes. For executed passed/failed tests also supply assertions: a nonempty list of exact account/error/state/balance assertions. Preserve the actual path/command used; final classification does not rename executed artifacts. Retain logs in the run directory and explain balances/authorization failures or other observable outcomes.

A passed test only proves its actual assertions; exploit/refutation truth remains the Judge's job. A failing compiler/fixture is blocked validation, not a successful exploit test. In skip-local-build mode use empty path/command and not-run/blocked. Info suggestions need no invented exploit.

Sources: [Anchor testing](https://www.anchor-lang.com/docs/testing).
