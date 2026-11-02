# Private Audit Output Contract

Standalone Anchor outputs use schema 2.0.0. Findings and pending questions keep independent collections; candidate ids remain stable while final presentation numbers may change. Gas denotes compute/rent optimization.

## Candidate data

candidates.json preserves review_type (vulnerability/trust-risk/design-risk/hardening/engineering-quality), scenario, applicability, existing_controls, recommendation, tradeoffs and missing_context alongside evidence, counterevidence and provenance. Per-source review_details retain disagreements after deduplication; different review types do not merge automatically. Audit context is retained at run level.

## Complete Judge

```json
{
  "schema_version": "2.0.0",
  "candidate_id": "finding-001",
  "review_status": "complete",
  "review_type": "trust-risk",
  "classification": "Info",
  "verdict": "Info",
  "title": "...",
  "finding_summary": "...",
  "required_conditions": [
    {
      "condition": "...",
      "status": "depend on role",
      "evidence": "..."
    }
  ],
  "reachability": "Known trusted-role operation; explain the specific gap.",
  "code_reality": "...",
  "protocol_semantics": "...",
  "impact": "...",
  "scenario": "Specific failure or protection gap; attacks need a concrete trace.",
  "applicability": "Why this matters to this project; identify inspected docs/tests for absence claims.",
  "existing_controls": "What is enforced, what is documented, and what remains unverified.",
  "recommendation": "Actionable proposed improvement, not a patch.",
  "tradeoffs": "Operational, compatibility and maintenance costs; explain if none identified.",
  "missing_context": [],
  "poc": {
    "path": "",
    "test_command": "",
    "test_result": "not-run",
    "notes": "Source evidence sufficient; no execution test performed."
  }
}
```

All illustrated fields are required except poc, whose default is empty/not-run. All five scenario/applicability/existing_controls/recommendation/tradeoffs fields require nonempty text; explain unknown/not applicable explicitly. Complete results require missing_context empty and an exact classification/verdict. Invalid additionally requires nonempty rejection_reason, explaining refutation or unmet reporting threshold. Use triage-policy.md for condition statuses and type/severity constraints.

## Pending Judge

```json
{
  "schema_version": "2.0.0",
  "candidate_id": "finding-001",
  "review_status": "needs_context",
  "review_type": "trust-risk",
  "title": "...",
  "finding_summary": "...",
  "scenario": "Specific failure or protection gap; attacks need a concrete trace.",
  "applicability": "Why this matters to this project; identify inspected docs/tests for absence claims.",
  "existing_controls": "What is enforced, what is documented, and what remains unverified.",
  "recommendation": "Actionable proposed improvement, not a patch.",
  "tradeoffs": "Operational, compatibility and maintenance costs; explain if none identified.",
  "missing_context": [
    {
      "question": "Which authority controls the program upgrade or token delegate in the audited deployment?",
      "required_evidence": "Program/mint address, cluster, slot reference and verified upgrade/delegate custody configuration."
    }
  ],
  "poc": {
    "path": "",
    "test_command": "",
    "test_result": "not-run",
    "notes": "Source evidence sufficient; no execution test performed."
  }
}
```

needs_context requires nonempty question and required_evidence strings for each missing-context item. Never include classification, verdict, severity or final_id, even null. Known partial reasoning may be included, but unresolved conditions must not be fabricated as false.

## Merge and resume

Every manifest candidate must have valid Judge JSON; missing files, duplicate ids, extra candidates and malformed records still block merging. apply-judges writes complete findings and pending_questions separately to results.json. Pending entries retain candidate_id, original candidate and source hypotheses, evidence, questions and Judge output. They have no final id or classification and do not affect severity counts. Coverage validation considers both collections. Supply new evidence to the same pending Judge, replace its output, then rerun apply-judges; do not recollect or renumber candidates merely to resume.

Completed final ids keep High -> H-n, Medium -> M-n, Low -> L-n, Info -> I-n, Gas -> G-n, Invalid -> Invalid-n. Candidate ids are the stable cross-run review reference; final presentation numbering can change when pending reviews finish.

## Human report

Drafts show candidate descriptions and scenarios without severity. Final wreport.md contains Finding Summary, Required Conditions, Reachability, Code Reality, Protocol Semantics, Impact, Verdict, Recommendation, Review Type, Scenario, Applicability, Existing Controls, Tradeoffs, Source Evidence and Validation. Include rejection reason for Invalid. A separate Pending Client Questions section lists unresolved candidates and required evidence without severity. Report skipped builds and unperformed PoCs explicitly; never imply execution validation from source review alone.

Executed PoCs require nonempty assertions alongside actual path and test_command. Report exact state/error/balance assertions and preserve original executed filenames. Build and test-framework readiness must permit execution; source-only or blocked modes cannot claim executed tests.
