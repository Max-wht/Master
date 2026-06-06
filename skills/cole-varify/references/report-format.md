# Report Format

`results.json` is the raw verification log. `report.md` is rendered from it and must deduplicate duplicate findings.

Top-level shape:

```json
{
  "schema_version": "1.0.0",
  "run_id": "20260529T051032Z-4e384be7",
  "project_root": "/path/to/project",
  "kai_run": "/path/to/MasterWu/Kai/runs/<run-id>",
  "findings": []
}
```

Each finding must include:

- `id`: merged Cole id such as `COLE-001`.
- `title`
- `source_hypotheses`
- `verification_status`
- `reachability`
- `nature`
- `evidence`
- `poc`: object with `path`, `test_command`, `test_result`, and `notes`.
- `reasoning`
- `final_recommendation`

Each finding may include:

- `dedupe_key`: explicit report-level merge key. If present, it overrides the fallback key.

Report-level dedupe:

- Do not rewrite `results.json`.
- Merge duplicate findings before rendering `report.md`.
- Prefer explicit `dedupe_key`; otherwise use title, nature, and evidence locations.
- Keep merged source hypotheses, evidence, reasoning, recommendations, and original ids.
- Prefer the strongest status: `confirmed > needs-poc > blocked-missing-context > blocked-build > rejected`.

`report.md` must include all deduped candidates, not only confirmed issues. Use these sections:

1. `# Cole Varify Report`
2. `## Summary`
3. `## Findings`
4. `## Build And Test Notes`
