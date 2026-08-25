---
name: cole-varify
description: "Validate Kai Research hypotheses after $kai-research. Use when Codex needs to preflight Solidity, Move, or Anchor builds, normalize and deduplicate Kai hypotheses, launch strict Judge subagents, reject fuzzy severity labels, create minimal runtime-appropriate PoCs, run local tests, and produce wreport.md under MasterWu/cole/."
---

# Cole Varify

Cole Varify turns Kai hypotheses into an evidence-backed verification report. Keep the user-requested `varify` spelling for the skill name.

## Quick Start

Resolve `$SKILL_DIR` to this skill directory, then run:

```bash
python3 "$SKILL_DIR/scripts/cole_varify.py" preflight <project-root> --run <project-root>/MasterWu/Kai/runs/<run-id>
python3 "$SKILL_DIR/scripts/cole_varify.py" collect <project-root> --run <project-root>/MasterWu/Kai/runs/<run-id> --out MasterWu/cole
python3 "$SKILL_DIR/scripts/cole_varify.py" prepare-judges <project-root>/MasterWu/cole/runs/<run-id>/candidates.json
```

Cole infers runtime from the Kai manifest. Override only for legacy runs:

```bash
python3 "$SKILL_DIR/scripts/cole_varify.py" preflight <project-root> --run <kai-run-dir> --runtime anchor
```

To skip local compilation and do only first-layer source logic review:

```bash
python3 "$SKILL_DIR/scripts/cole_varify.py" preflight <project-root> --run <project-root>/MasterWu/Kai/runs/<run-id> --skip-local-build
```

If preflight fails, stop. Do not write PoCs or verify hypotheses until the project builds. Report the failed command, error summary, and suggested build/install command from `MasterWu/cole/runs/<run-id>/build-blocker.md`.

If `--skip-local-build` is used, continue only in logic-only mode: do not create PoCs, do not run tests, and do not assign `High`, `Medium`, or `Low` without exact source-level evidence.

## Workflow

1. **Preflight first.** Validate the Kai run, ensure reports are complete, detect the build system, and run the minimum build command. If the project does not build, stop. With `--skip-local-build`, skip build detection and continue only with first-layer source logic review.
2. **Collect candidates.** Run `collect` to write normalized and deduplicated hypotheses to `MasterWu/cole/runs/<run-id>/candidates.json` and a draft `wreport.md`.
3. **Prepare strict Judge tasks.** Run `prepare-judges` to create one bundle per deduped finding under `MasterWu/cole/runs/<run-id>/judges/`.
4. **Launch Judge subagents in waves of at most 6.** Each subagent reads only its `bundle.md`, writes `judge.json` and `judge.md`, and must classify the finding exactly as `High`, `Medium`, `Low`, `Info`, `Gas`, or `Invalid`.
5. **Reject fuzzy output.** Run `validate-judges`. If a Judge returns a fuzzy label, missing proof, or asks for more context, do not merge it; follow up with that subagent until it returns one exact classification.
6. **Create PoCs only after triage and only when preflight status is `passed`.** Read `references/poc-policy.md` before writing tests. Use non-Cole runtime-specific PoC names and do not modify target contracts or modules. In `skipped-local-build` mode, do not create PoCs or run tests.
7. **Write final results and report.** Run `apply-judges` to write `results.json` and overwrite `wreport.md` with the strict Judge sections.

```bash
python3 "$SKILL_DIR/scripts/cole_varify.py" validate-judges MasterWu/cole/runs/<run-id>/judges/manifest.json
python3 "$SKILL_DIR/scripts/cole_varify.py" apply-judges MasterWu/cole/runs/<run-id>/candidates.json
python3 "$SKILL_DIR/scripts/cole_varify.py" validate-results MasterWu/cole/runs/<run-id>/results.json --candidates MasterWu/cole/runs/<run-id>/candidates.json
```

## Judge Subagents

When using Codex, launch Judge tasks from `judges/manifest.json` with `multi_agent_v1.spawn_agent` in batches of at most 6. Give each subagent only its assigned `bundle.md` path and tell it to write the configured `judge.json` and `judge.md`. Close completed agents before launching the next batch.

If `validate-judges` fails because a Judge output is fuzzy or incomplete, send that same subagent the validation error and ask it to return one exact classification. Do not run `apply-judges` until every Judge output validates.

## Output Contract

Default output root is `MasterWu/cole/`. For a Kai run id `<run-id>`, Cole writes:

- `MasterWu/cole/runs/<run-id>/preflight.json` when build preflight passes or local build is skipped.
- `MasterWu/cole/runs/<run-id>/build-blocker.md` when build preflight fails.
- `MasterWu/cole/runs/<run-id>/candidates.json` after collection.
- `MasterWu/cole/runs/<run-id>/wreport.md` as the draft after collection and as the final report after Judge merge.
- `MasterWu/cole/runs/<run-id>/judges/manifest.json` plus one Judge bundle per finding.
- `MasterWu/cole/runs/<run-id>/results.json` after strict Judge merge.

When `preflight.json` has `status: "skipped-local-build"`, results must use empty PoC path and command, `poc.test_result: "not-run"` or `"blocked"`, and report that local build was skipped and PoC validation was not performed.

Every final result item must include:

- `candidate_id`: internal `finding-001` style id.
- `final_id`: `[H-1]`, `[M-1]`, `[L-1]`, `[I-1]`, `[G-1]`, or `[Invalid-1]` style id without brackets in JSON.
- `classification`: exactly `High`, `Medium`, `Low`, `Info`, `Gas`, or `Invalid`.
- `required_conditions[].status`: exactly `true`, `false`, or `depend on role`; never `Unproven`.
- source hypotheses, evidence, PoC path/test command/test result, and the full strict Judge result.

No final output may use labels such as `Conditional Medium`, `Potential High`, `Possible Low`, `Likely Valid`, or a separate missing-proof bucket. If proof is missing, the Judge must ask for the exact missing context instead of producing a mergeable result.

## References

- `references/build-detection.md`: build-system detection and blocker handling.
- `references/triage-policy.md`: reachability, design-vs-bug, and verdict rules.
- `references/poc-policy.md`: PoC directory, test scope, and safety rules.
- `references/report-format.md`: `results.json`, Judge output, and `wreport.md` formatting.
- `references/judge-rubric.md`: strict condition-by-condition Judge rubric.
