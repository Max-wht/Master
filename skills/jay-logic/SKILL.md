---
name: jay-logic
description: "Function-level smart contract logic mapping for audit preparation. Use when Codex needs to map which functions, source lines, state variables, guards, internal calls, external calls, value transfers, or state transitions are related in Solidity, Move, or another contract language before a security review."
---

# Jay Logic

Generate a function-first logic map for smart contract repositories. The output is audit navigation material, not a vulnerability verdict.

## Quick Start

Resolve `$SKILL_DIR` to the directory containing this `SKILL.md`, then run:

```bash
python3 "$SKILL_DIR/scripts/jay_logic.py" build <project-root> --out MasterWu/Jay --lang auto
python3 "$SKILL_DIR/scripts/jay_logic.py" validate <project-root>/MasterWu/Jay/jay-logic.json
```

If the user does not provide a project root, use the current working directory. Keep the default repo-local output directory `MasterWu/Jay/` unless the user asks for another path.

For an explicit file set, pass repo-relative Solidity/Move files:

```bash
python3 "$SKILL_DIR/scripts/jay_logic.py" build <project-root> --out MasterWu/Jay --lang solidity --files src/Vault.sol src/Strategy.sol
```

## Workflow

1. Build the canonical graph with `scripts/jay_logic.py build`.
2. Read `MasterWu/Jay/functions.md` first for the function-by-function audit map.
3. Use `MasterWu/Jay/line-links.tsv` when the user asks which logic is related to a specific line.
4. Use Mermaid files for quick visualization:
   - `MasterWu/Jay/call-graph.mmd`
   - `MasterWu/Jay/storage-flow.mmd`
5. Use `MasterWu/Jay/jay-logic.json` as the machine-readable source of truth for follow-up tooling.

## Output Contract

The build command writes:

- `MasterWu/Jay/jay-logic.json` - canonical graph IR.
- `MasterWu/Jay/functions.md` - function responsibilities, calls, reads, writes, guards, and external interactions.
- `MasterWu/Jay/line-links.tsv` - `file:line` to related node and edge ids.
- `MasterWu/Jay/call-graph.mmd` - Mermaid function call graph.
- `MasterWu/Jay/storage-flow.mmd` - Mermaid state/resource flow graph.
- `MasterWu/Jay/entry-flows.md` - entry-oriented paths from callable functions to state, guards, and external calls.

## Language Strategy

Use adapter-based extraction. The core schema is language-neutral; language assumptions belong only in adapter modules.

- `solidity` extracts contracts, functions, modifiers/guards, state vars, events, calls, ERC20-like transfers, native value calls, and simple state transitions.
- `move` extracts modules, public/entry functions, resources, `acquires`, resource reads/writes, guards, and module calls.
- `generic` is a low-confidence fallback for unsupported languages.

For detailed schema or adapter rules, read only the reference needed:

- `references/schema.md` for JSON node/edge fields.
- `references/adapter-contract.md` before adding a new language adapter.
- `references/workflow.md` for operational interpretation of the output.

## Accuracy Rules

- Treat line numbers and code references as evidence; do not invent edges not present in the graph.
- If an edge has low confidence, say so instead of using it as a definitive audit fact.
- Do not classify vulnerabilities from Jay Logic output alone. Use it to choose paths for later audit validation.
- If a user asks for a specific line, start from `line-links.tsv`, then open the source and the corresponding function in `functions.md`.
