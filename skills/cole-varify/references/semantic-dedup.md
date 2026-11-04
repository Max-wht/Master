# Global semantic grouping before Judge dispatch

The parent agent performs this stage after all Kai outputs validate. Do not launch
another research agent, filter candidate validity, or assign severity here.
Scripts validate the partition and provenance; they do not infer equivalence.

## Review all candidates

`collect` writes `raw-candidates.json`, a full navigation index in
`dedup-bundle.md`, and a pending `dedup-decisions.json` template. It does not
deduplicate by title/claim/category/file hashes or create final candidates.
Each raw record has a unique `source_id`, source identity, the complete original
`hypothesis`, and a normalized representation. The input digest binds research
outputs, manifest, available source snapshots and referenced/scoped source files.

Read the full index, all raw hypotheses, then relevant exact source and context.
Compare concrete root cause, failure mechanism, necessary conditions and repair
site across every specialist. Changes in wording, category or evidence files do
not make a claim independent. Different functions can merge only for a shared
cause resolved by the same repair. Keep independent causes, independently
necessary conditions, and different `review_type` values separate. Keep uncertain
duplicates separate and record the uncertainty in the singleton rationale.

For large runs, read details in batches while maintaining one global group index.
Finish cross-batch comparisons before declaring completion. File/category/graph
buckets help navigation but must not exclude comparisons across buckets.

## Decisions contract

Keep the generated `run_id` and `input_digest`. Replace the pending template after
actual global review. Every source id must occur exactly once, including singleton
groups; no excluded, invalid, severity or verdict fields are accepted.

```json
{
  "schema_version": "1.0.0",
  "run_id": "research-run",
  "input_digest": "<generated sha256>",
  "review_status": "complete",
  "groups": [
    {
      "member_ids": ["01-math-precision:KAI-01-001", "05-invariant:KAI-05-002"],
      "title": "Canonical description of the shared defect",
      "claim": "One concrete claim retaining the group's relevant conditions.",
      "root_cause": "The same missing invariant or incorrect state transition at the shared repair site.",
      "rationale": "Explain shared mechanism/conditions/repair; for singletons explain independence or uncertainty."
    }
  ]
}
```

All four group text fields must be nonempty. The script rejects missing/duplicate
members, unknown ids, cross-type groups, wrong runs/digests and incomplete review.
A zero-candidate run is completed automatically with an empty partition.

## Apply, lock and resume

Run `apply-dedup <raw-candidates.json> --decisions <dedup-decisions.json>`.
It writes final `candidates.json`, validated decisions and membership mapping in
`dedup-record.json`, and draft `wreport.md`. Final candidates retain existing
schema `2.0.0`, adding `member_ids`, `root_cause`, `dedup_rationale` and complete
`source_records`. Aggregated evidence, Jay refs, conditions/scenarios, counterevidence,
recommendations and missing-context questions remain available to the Judge.
Candidate `source_records` are original records, not canonical-summary replacements.
Run-level `deduplication` records completion, method and digests; `dedup_stats`
records raw/group/reduced counts and reduction ratio. Reports display these counts.

`prepare-judges` reconstructs and validates the handoff before creating one Judge
per group. Its manifest binds candidate contents; `.judge-lock.json` in the Cole
run directory locks grouping even when Judge output uses a custom directory.
After dispatch, a changed grouping or research input requires a new Cole run
(use a different `collect --out` root if reusing unchanged research). Refreshing
preflight or a pending Judge does not change candidate identity. New evidence for
a pending review belongs in its Judge, not in edited Kai outputs. Recollect/apply
with identical input is idempotent and preserves completed reports.

Historical candidate inputs remain readable. New dispatch without semantic
metadata requires explicit `prepare-judges --allow-legacy-candidates` and is
marked as lacking semantic deduplication. This flag cannot bypass invalid semantic
metadata. Old Judge/results inputs remain readable without migration. Build/PoC
readiness and classification rules are unchanged.
