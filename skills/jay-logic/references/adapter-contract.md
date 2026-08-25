# Adapter Contract

Adapters translate language-specific syntax into the Jay Logic graph schema.

## Required Functions

Each adapter module must expose:

```python
LANGUAGE = "language-name"

def detect(project_root: Path) -> bool:
    ...

def collect(project_root: Path) -> dict:
    ...
```

`collect()` returns:

```python
{
    "language": "solidity",
    "nodes": [...],
    "edges": [...]
}
```

The core CLI handles schema validation, post-processing, markdown rendering, Mermaid rendering, and `line-links.tsv`.

## Extraction Rules

- Keep ids stable across runs by deriving them from repo-relative path, symbol name, and line number.
- Preserve source line evidence for every node and edge.
- Prefer `medium` or `low` confidence when syntax is inferred by regex rather than an AST.
- Do not encode vulnerability classifications in adapter output.
- If a language supports explicit entry points, mark them in node metadata with `entry_point: true`.

## Adding Languages

Add a new adapter file under `scripts/adapters/`, import it in `scripts/jay_logic.py`, and update the `--lang` choices. Do not change the core JSON schema unless the existing node/edge model cannot represent the language.

Runtime-specific details should live in `metadata`, not new top-level schema fields. Examples: `runtime_profile`, `entry_point`, Move capability/resource facts, Anchor context names, account constraints, PDA/seeds, signer fields, token program facts, or CPI classification.
