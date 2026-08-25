# Report Format

`candidates.json` keeps the deduped Kai hypotheses. `wreport.md` is the human report. `results.json` is written only after strict Judge outputs are merged.

## Candidate IDs

Candidates use internal ids only:

```text
finding-001
finding-002
```

Do not expose old finding prefixes in report headings, PoC filenames, or test commands.

## Draft wreport

`collect` writes `MasterWu/cole/runs/<run-id>/wreport.md` with one section per deduped candidate:

```markdown
## Finding 1: title
<!-- candidate_id: finding-001 -->

### Description

### Impact
```

The draft has no severity. Severity is assigned only after Judge validation.

## Judge Output

Each Judge writes `judge.json` with:

```json
{
  "schema_version": "1.0.0",
  "candidate_id": "finding-001",
  "classification": "High",
  "verdict": "High",
  "title": "Finding title",
  "finding_summary": "...",
  "required_conditions": [
    {"condition": "...", "status": "true", "evidence": "..."}
  ],
  "reachability": "...",
  "code_reality": "...",
  "protocol_semantics": "...",
  "impact": "...",
  "bounty_recommendation": "Submit bounty",
  "poc": {"path": "", "test_command": "", "test_result": "not-run", "notes": ""}
}
```

`classification` and `verdict` must be exactly one of:

```text
High
Medium
Low
Info
Gas
Invalid
```

Do not accept fuzzy labels such as conditional severity, possible severity, likely validity, or any separate missing-proof bucket. If evidence is not enough for an exact classification, the Judge must ask for the missing context instead of writing a mergeable `judge.json`.

`required_conditions[].status` must be exactly one of:

```text
true
false
depend on role
```

Do not use `Unproven`, `unknown`, `unclear`, or similar labels. Missing proof must become `false`, role-only reachability must become `depend on role`, or the Judge must ask for more evidence before writing `judge.json`.

## Final IDs

`apply-judges` assigns final ids in report order:

```text
High -> H-1, H-2
Medium -> M-1, M-2
Low -> L-1, L-2
Info -> I-1, I-2
Gas -> G-1, G-2
Invalid -> Invalid-1, Invalid-2
```

Final `wreport.md` headings use bracketed ids:

```markdown
## [H-1] Finding title
```

## Final wreport Sections

Each final finding must contain:

```markdown
### Finding Summary
### Required Conditions
### Reachability
### Code Reality
### Protocol Semantics
### Impact
### Verdict
### Bounty Recommendation
```
