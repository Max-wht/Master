# Graph and Business Map Contract

jay-logic.json uses schema 1.0.0: generated_at, project_root, languages, nodes, edges, line_links, stats. Nodes: function, statement, state_var, guard, event, external_symbol, contract_or_module. Edges: calls, reads, writes, guards, emits, external_call, transfers_value, state_transition, precondition_written_by. Node/edge evidence uses repo-relative files and one-based line ranges. Metadata holds crate/module, Rust source hashes, Cargo/lockfile/Anchor configuration fingerprints (including observed absence), versions, constraints and coverage gaps.

audit-map.json is independently AI-authored schema 1.0.0. Preserve generated graph_digest. Validation checks digest, source freshness, node references and evidence ranges. A changed rebuild archives prior semantics.

```json
{
  "schema_version": "1.0.0",
  "graph_digest": "preserve-generated-value",
  "review_status": "complete",
  "completion_notes": "Describe inspected flows, non-applicable categories and remaining gaps.",
  "semantics": [{
    "kind": "invariant",
    "provenance": "inference",
    "description": "Tracked shares must reconcile with accepted assets; investigate transfer-fee effects.",
    "node_ids": ["existing-node-id"],
    "evidence": [{"file": "programs/vault/src/lib.rs", "start_line": 12, "end_line": 30}]
  }]
}
```

Kinds: protocol-summary, asset-flow, lifecycle, state-transition, invariant, external-assumption. Provenance: source-fact, inference, unresolved. Unresolved entries state the exact missing fact/evidence. No severity or final verdicts.

The generated review_status is needs_ai_review. Complete requires nonempty sourced semantics and completion_notes. Include a protocol summary and consequential applicable flows/invariants; do not manufacture irrelevant categories. AI may add supplemental account/control facts anchored to source but must not overwrite graph facts.
