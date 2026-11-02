# Report Formatting

Write report.md with Scope Read (including supporting docs/tests/config and limitations), Candidate Hypotheses, Rejected Leads, and Validation Queue. Background privilege maps belong in Scope Read, not findings. Candidates include their review type, scenario, source evidence, applicability, existing controls, recommendation/tradeoffs, counterevidence and missing-context questions.

Write hypotheses.json using schema 2.0.0. No severity, verdict, confirmed, or final_verdict. Confidence is low/medium/high. Review type is one of vulnerability, trust-risk, design-risk, hardening, engineering-quality; category remains the technical topic.

```json
{
  "schema_version": "2.0.0",
  "run_id": "...",
  "agent_id": 2,
  "agent_name": "access-control",
  "hypotheses": [
    {
      "id": "KAI-02-001",
      "title": "...",
      "claim": "...",
      "category": "access-control",
      "review_type": "trust-risk",
      "confidence": "medium",
      "evidence": [
        {
          "file": "src/Vault.sol",
          "start_line": 10,
          "end_line": 40
        }
      ],
      "jay_refs": {
        "node_ids": [],
        "edge_ids": []
      },
      "scenario": "Specific failure or protection gap; attacks need a concrete trace.",
      "applicability": "Why this matters to this project; identify inspected docs/tests for absence claims.",
      "existing_controls": "What is enforced, what is documented, and what remains unverified.",
      "recommendation": "Actionable proposed improvement, not a patch.",
      "tradeoffs": "Operational, compatibility and maintenance costs; explain if none identified.",
      "missing_context": [],
      "why_might_be_real": "...",
      "why_might_be_false_positive": "Specific counterevidence or compensating controls to verify.",
      "next_validation_steps": [
        "..."
      ]
    }
  ]
}
```

All illustrated fields are required. The five text fields scenario/applicability/existing_controls/recommendation/tradeoffs must be nonempty; explicitly explain unknown/not applicable rather than inventing a fact. missing_context is a list of objects with nonempty question and required_evidence strings. An empty list means no known missing context, not that Kai has issued a final verdict.

Specialist evidence fields may be added; they do not replace the common fields. Use scenario for attack, failure, or improvement reasoning; do not invent exploits for Info candidates. Readers still accept schema 1.0.0 with attack_sketch and normalize legacy records as vulnerability candidates.
