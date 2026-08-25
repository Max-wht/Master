---
name: kai-research
description: "Jay-guided large smart-contract vulnerability hypothesis search. Use when Codex needs to prepare and run parallel specialist agents over Solidity, Move, or Anchor code to find candidate vulnerabilities, evidence paths, and validation leads without writing PoCs, modifying target code, or issuing final vulnerability verdicts."
---

# Kai Research

Prepare Jay-guided bundles for large Solidity, Move, or Anchor audits, then run 12 specialist agents in parallel. Kai searches for candidate vulnerabilities only; a later validation skill must prove or reject them.

## Quick Start

Resolve `$SKILL_DIR` to the directory containing this `SKILL.md`, then run:

```bash
python3 "$SKILL_DIR/scripts/kai_prepare.py" prepare <project-root>
```

Select one runtime per run when a repository contains multiple runtimes:

```bash
python3 "$SKILL_DIR/scripts/kai_prepare.py" prepare <project-root> --lang move
python3 "$SKILL_DIR/scripts/kai_prepare.py" prepare <project-root> --lang anchor
```

For explicit source files:

```bash
python3 "$SKILL_DIR/scripts/kai_prepare.py" prepare <project-root> --files src/Vault.sol src/Strategy.sol
python3 "$SKILL_DIR/scripts/kai_prepare.py" prepare <project-root> --lang anchor --files programs/vault/src/lib.rs
```

If the user does not provide a project root, use the current working directory. Kai writes worktree artifacts under `MasterWu/Kai/runs/<run-id>/` and requires sibling skill `jay-logic`; stop if Jay is unavailable or fails validation.

## Workflow

### Turn 1: Discover

1. Print a short banner naming Kai and the project root.
2. Confirm one in-scope runtime: `solidity`, `move`, or `anchor`. If auto-detection sees multiple runtimes, stop and require `--lang` or explicit `--files`.
3. Confirm source files for that runtime. Default exclusions still remove generated, dependency, test, mock, and `MasterWu/` artifacts. Explicit `--files` overrides directory exclusions but must stay inside the project and match the selected runtime.
4. Locate sibling `jay-logic` under the same parent skill directory.

### Turn 2: Prepare

1. Run Jay into `MasterWu/Jay/` and validate `MasterWu/Jay/jay-logic.json`.
2. Build `MasterWu/Kai/runs/<run-id>/source.md` from all in-scope source files with runtime-appropriate code fences.
3. Build 12 Jay graph slices from `MasterWu/Jay/jay-logic.json`, `functions.md`, `entry-flows.md`, and `line-links.tsv`.
4. Build one bundle per agent:
   - full `source.md`
   - `references/shared-rules.md`
   - `references/runtime-semantics.md`
   - `references/judging.md`
   - `references/report-formatting.md`
   - `references/senior-auditor-sop.md`
   - that agent's specialist reference file
   - that agent's Jay slice
5. Write `spawn-manifest.json` with agent ids, bundle paths, and output paths.

### Turn 3: Run 12 Agents

Spawn all 12 agents in one round from `spawn-manifest.json`. Do not let child agents wander the repository first; each child agent must read its own `bundle.md`, then write only:

```text
agents/<id-name>/report.md
agents/<id-name>/hypotheses.json
```

Run agents 1-12 concurrently, then wait for completion. Do not create a central summary report. After completion, check that each `report.md` no longer contains `PENDING_KAI_AGENT_OUTPUT` and each `hypotheses.json` validates:

```bash
python3 "$SKILL_DIR/scripts/kai_prepare.py" validate-hypotheses <path/to/hypotheses.json>
```

## Agents

1. `math-precision`: rounding, decimal scale, casts, overflows, precision loss.
2. `access-control`: permissions, initialization, role escalation, proxy/delegatecall.
3. `economic-security`: token behavior, external dependencies, prices, incentives, flash-loan value extraction.
4. `execution-trace`: entry-to-state paths, cross-transaction state, branching, external calls.
5. `invariant`: conservation, coupled state, caps, view/write consistency.
6. `periphery`: helper, library, encoder, wrapper, base contract surfaces.
7. `first-principles`: invalid protocol assumptions.
8. `asymmetry`: paired functions, branch variants, admin/user variants, read/write asymmetry.
9. `boundary`: external calls, payable, sentinel addresses, bytes decode, boundary values.
10. `numerical-gap`: precision x invariant x boundary gaps.
11. `trust-gap`: access x economics x asymmetry gaps.
12. `flow-gap`: execution x periphery x protocol-intent gaps.

## Runtime Rules

- Use `references/runtime-semantics.md` before translating an EVM idea into Move or Anchor.
- In Move, entry points, signer/resource/capability boundaries, and type identity are the core evidence.
- In Anchor, instruction handlers, account constraints, signer bits, PDA seeds, account owner/discriminator, CPI targets, token program, mint, token-account owner, and lamport/token deltas are the core evidence.
- Do not create a fake cross-runtime call graph in mixed repositories. Run one runtime at a time and connect components only through explicit bridge/message/CPI/binding boundaries.

## Output Contract

Each `hypotheses.json` must use schema version `1.0.0` and contain only vulnerability hypotheses, not final verdicts or severity ratings. Every hypothesis needs source evidence, Jay refs when available, an attack sketch, false-positive reasons, and next validation steps.

## References

- `references/shared-rules.md`: global constraints all agents must follow.
- `references/runtime-semantics.md`: Solidity / Move / Anchor semantic mapping.
- `references/judging.md`: candidate confidence policy.
- `references/report-formatting.md`: Markdown and JSON output contract.
- `references/senior-auditor-sop.md`: search procedure.
- `references/subAgents/agent-*.md`: specialist assignments.
