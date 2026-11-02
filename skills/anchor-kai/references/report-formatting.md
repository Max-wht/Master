# Hypothesis Contract

Write schema 2.0.0 with run_id, agent_id (1..12), agent_name and hypotheses. Use the assigned manifest identity. A completed report removes PENDING_KAI_AGENT_OUTPUT even when hypotheses is empty.

Each hypothesis has:
- id (KAI-<two-digit-agent>-<three-digit-sequence>), title, claim, category, confidence (low/medium/high).
- review_type: vulnerability, trust-risk, design-risk, hardening or engineering-quality.
- evidence: nonempty list of {file, start_line, end_line}; repo-relative files, positive one-based ordered ranges.
- jay_refs: {node_ids: [], edge_ids: []}, using the snapshotted graph; unavailable refs may be empty.
- scenario, applicability, existing_controls, recommendation, tradeoffs: nonempty text; explicitly explain unknown/non-applicable details.
- why_might_be_real, why_might_be_false_positive: concrete supporting and refuting reasons.
- next_validation_steps: nonempty list of actionable checks.
- missing_context: [] or [{question: "...", required_evidence: "..."}].

Specialists may add source-backed role-specific evidence (e.g. authority_chain, balance_deltas, paired_paths), which normalization retains. Do not include severity, verdict, classification, final_id, final_verdict or confirmed.
