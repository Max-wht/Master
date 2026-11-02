---
name: anchor-kai
description: Run twelve Anchor DeFi research specialists from a reviewed anchor-jay map. Use for vulnerability, trust/design risk, hardening and engineering candidates with native Solana evidence; verification and PoCs belong to anchor-cole.
---

# Anchor Kai

Research Anchor DeFi candidates using the standalone anchor-jay -> anchor-kai -> anchor-cole pipeline. Resolve this skill directory as SKILL_DIR. Require the sibling anchor-jay skill and its pinned Python AST dependencies.

## Prepare and research

1. Use $anchor-jay to build and complete the AI business map first. Read its coverage gaps; a successful extraction is not a completed business review.
2. Prepare the twelve specialist bundles:

```bash
python3 "$SKILL_DIR/scripts/anchor_kai.py" prepare <project-root> --context audit-context.md --run-id <run-id>
```

Omit optional context/run-id as appropriate. --files seeds an explicit module closure; a changed scope requires another Jay semantic review. An absent map is built but preparation stops until the AI completes it. No target build is required.

3. Read MasterWu/Anchor/Kai/runs/<run-id>/spawn-manifest.json. Launch the twelve research agents using the available native subagent tool, in waves respecting the host's actual concurrency limit. Give each agent only its assigned bundle path and spawn_prompt. Each bundle includes the full line-numbered source, reviewed business map, specialized graph slice and context/material index.
4. Each agent reads its bundle completely, then relevant indexed source/docs/tests/dependencies. Replace the pending marker in report.md and write hypotheses.json; an empty candidate list is valid after actual review. Do not invent candidates to meet a quota, create PoCs or modify target code.
5. Validate every output, resolving structural errors with the same specialist. Preserve candidate uncertainties and counterevidence; parallel convergence is not proof.

```bash
python3 "$SKILL_DIR/scripts/anchor_kai.py" validate-hypotheses <agent-dir>/hypotheses.json
```

Then invoke $anchor-cole. Graph, business map, source and client context are snapshotted per run. Source changes require a new research run.

## References

- references/shared-rules.md: evidence gates and research discipline.
- references/runtime-semantics.md: native Anchor rules and false-positive controls.
- references/report-formatting.md: schema 2.0.0 hypotheses.
- references/specialists/: the twelve role-specific research instructions included in bundles.
