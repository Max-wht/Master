---
name: cole-varify
description: "Validate Kai Research hypotheses after $kai-research. Use when Codex needs to preflight a Solidity project build, normalize and deduplicate Kai hypotheses, judge ordinary-user reachability versus design/trusted-role/configuration risk, create minimal PoCs under test/MasterWuCole/, run local tests, and produce a verification report under MasterWu/cole/."
---

# Cole Varify

Cole Varify turns Kai hypotheses into an evidence-backed verification report. Keep the user-requested `varify` spelling for the skill name.

## Quick Start

Resolve `$SKILL_DIR` to this skill directory, then run:

```bash
python3 "$SKILL_DIR/scripts/cole_varify.py" preflight <project-root> --run <project-root>/MasterWu/Kai/runs/<run-id>
python3 "$SKILL_DIR/scripts/cole_varify.py" collect <project-root> --run <project-root>/MasterWu/Kai/runs/<run-id> --out MasterWu/cole
```

To skip local compilation and do only first-layer source logic review:

```bash
python3 "$SKILL_DIR/scripts/cole_varify.py" preflight <project-root> --run <project-root>/MasterWu/Kai/runs/<run-id> --skip-local-build
```

If preflight fails, stop. Do not write PoCs or verify hypotheses until the project builds. Report the failed command, error summary, and suggested build/install command from `MasterWu/cole/runs/<run-id>/build-blocker.md`.

If `--skip-local-build` is used, continue only in logic-only mode: do not create PoCs, do not run tests, and do not treat a `needs-poc` candidate as confirmed.

## Workflow

1. **Preflight first.** Validate the Kai run, ensure reports are complete, detect the build system, and run the minimum build command. If the project does not build, stop. With `--skip-local-build`, skip build detection and continue only with first-layer source logic review.
2. **Collect candidates.** Run `collect` to write normalized and deduplicated hypotheses to `MasterWu/cole/runs/<run-id>/candidates.json`.
3. **Triage with source evidence.** Read `references/triage-policy.md`. For every candidate, open the cited source lines, nearby tests, and Jay refs when useful. Never confirm a bug from Kai text alone.
4. **Create PoCs only after triage and only when preflight status is `passed`.** Read `references/poc-policy.md` before writing tests. Put PoCs under `test/MasterWuCole/` and do not modify target contracts. In `skipped-local-build` mode, do not create PoCs or run tests.
5. **Write results and report.** Fill `MasterWu/cole/runs/<run-id>/results.json`, run `validate-results`, then render a deduplicated `report.md`.

```bash
python3 "$SKILL_DIR/scripts/cole_varify.py" validate-results MasterWu/cole/runs/<run-id>/results.json --candidates MasterWu/cole/runs/<run-id>/candidates.json
python3 "$SKILL_DIR/scripts/cole_varify.py" render-report MasterWu/cole/runs/<run-id>/results.json --out MasterWu/cole/runs/<run-id>/report.md
```

## Output Contract

Default output root is `MasterWu/cole/`. For a Kai run id `<run-id>`, Cole writes:

- `MasterWu/cole/runs/<run-id>/preflight.json` when build preflight passes or local build is skipped.
- `MasterWu/cole/runs/<run-id>/build-blocker.md` when build preflight fails.
- `MasterWu/cole/runs/<run-id>/candidates.json` after collection.
- `MasterWu/cole/runs/<run-id>/results.json` after manual verification.
- `MasterWu/cole/runs/<run-id>/report.md` as the deduplicated final verification report.

When `preflight.json` has `status: "skipped-local-build"`, results must use empty PoC path and command, `poc.test_result: "not-run"` or `"blocked"`, and report that local build was skipped and PoC validation was not performed.

Every result item must include:

- `verification_status`: `confirmed`, `rejected`, `needs-poc`, `blocked-build`, or `blocked-missing-context`.
- `reachability`: `ordinary-user-reachable`, `trusted-role-only`, `governance-only`, `configuration-dependent`, or `unreachable`.
- `nature`: `real-bug`, `design-choice`, `configuration-risk`, `trusted-role-risk`, or `false-positive`.
- evidence, source Kai hypotheses, PoC path/test command/test result, reasoning, and final recommendation.

Final report dedupe happens only during `render-report`: `results.json` remains the raw per-candidate verification log, while `report.md` merges duplicate findings and shows both raw and deduped counts.

## References

- `references/build-detection.md`: build-system detection and blocker handling.
- `references/triage-policy.md`: reachability, design-vs-bug, and verdict rules.
- `references/poc-policy.md`: PoC directory, test scope, and safety rules.
- `references/report-format.md`: `results.json` and `report.md` formatting.
