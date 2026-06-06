# Report Formatting

Write `report.md` with these sections:

1. `# Kai Agent NN: Name`
2. `## Scope Read`
3. `## Candidate Hypotheses`
4. `## Rejected Leads`
5. `## Validation Queue`

Write `hypotheses.json` with this shape:

```json
{
  "schema_version": "1.0.0",
  "run_id": "...",
  "agent_id": 1,
  "agent_name": "math-precision",
  "hypotheses": [
    {
      "id": "KAI-01-001",
      "title": "...",
      "claim": "...",
      "category": "...",
      "confidence": "low",
      "evidence": [
        {"file": "src/Vault.sol", "start_line": 10, "end_line": 40}
      ],
      "jay_refs": {
        "node_ids": [],
        "edge_ids": []
      },
      "attack_sketch": "...",
      "why_might_be_real": "...",
      "why_might_be_false_positive": "...",
      "next_validation_steps": []
    }
  ]
}
```

Do not add `severity`, `verdict`, `confirmed`, or `final_verdict`.
