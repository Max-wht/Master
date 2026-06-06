# Jay Logic Schema

`jay-logic.json` is the canonical artifact. Markdown, TSV, and Mermaid files are rendered from it.

## Top-Level Object

Required fields:

- `schema_version`: string, currently `1.0.0`.
- `generated_at`: ISO-8601 UTC timestamp.
- `project_root`: absolute project root used for extraction.
- `languages`: detected language adapters used.
- `nodes`: graph nodes.
- `edges`: graph edges.
- `line_links`: per-line reverse index.
- `stats`: summary counts.

## Nodes

Required node fields:

- `id`: stable string id.
- `type`: one of `function`, `statement`, `state_var`, `guard`, `event`, `external_symbol`, `contract_or_module`.
- `language`: adapter language name.
- `file`: repo-relative path.
- `name`: short display name.
- `signature`: function/module/state signature or display text.
- `start_line`: 1-based line.
- `end_line`: 1-based line.
- `confidence`: `high`, `medium`, or `low`.
- `source_adapter`: adapter name.

Optional fields:

- `parent_id`: enclosing contract/module/function node.
- `visibility`: language-specific callable visibility.
- `metadata`: adapter-specific facts that do not affect schema compatibility.

## Edges

Required edge fields:

- `id`: stable string id.
- `type`: one of `calls`, `reads`, `writes`, `guards`, `emits`, `external_call`, `transfers_value`, `state_transition`, `precondition_written_by`.
- `from`: source node id.
- `to`: destination node id.
- `file`: repo-relative path for the evidence line.
- `start_line`: 1-based line.
- `end_line`: 1-based line.
- `label`: short evidence label.
- `confidence`: `high`, `medium`, or `low`.
- `source_adapter`: adapter name.

## Line Links

Each line link maps a source line to graph ids:

- `file`
- `line`
- `node_ids`
- `edge_ids`

For a function body line, the function node should appear in `node_ids`. For a guard/call/write/read line, the relevant edge id should appear in `edge_ids`.
