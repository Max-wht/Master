---
name: anchor-cole
description: Independently validate anchor-kai candidates, merge complete and pending reviews, and report Anchor DeFi findings. Uses source-first private-audit gates with on-demand build/PoC readiness for existing project test frameworks.
---

# Anchor Cole

Verify the standalone Anchor Kai run; do not call cole-varify or search for unrelated findings. Resolve this skill directory as SKILL_DIR. Read references/triage-policy.md and references/judge-rubric.md before classification.

## Source-first workflow

1. Collect completed research. No build preflight is required:

```bash
python3 "$SKILL_DIR/scripts/anchor_cole.py" collect <project-root> --run <anchor-kai-run>
# Parent reads dedup-bundle.md and completes dedup-decisions.json first.
python3 "$SKILL_DIR/scripts/anchor_cole.py" apply-dedup <raw-candidates.json> --decisions <dedup-decisions.json>
python3 "$SKILL_DIR/scripts/anchor_cole.py" prepare-judges <candidates.json>
```

The collector rejects pending reports, wrong run/agent identities, missing/stale snapshots and invalid source/graph references. Output: MasterWu/Anchor/Cole/runs/<run-id>/. It writes all original hypotheses to raw-candidates.json, a full index in dedup-bundle.md and pending dedup-decisions.json. The parent reads [semantic-dedup.md](references/semantic-dedup.md), compares all candidates by root cause/mechanism/conditions/repair site across specialists and batches, then writes a complete partition including singletons. Keep different review types and uncertain duplicates separate. Grouping does not assign validity or severity. apply-dedup validates coverage/provenance before writing candidates.json, dedup-record.json and draft wreport.md. No Judge may start before completion.

prepare-judges binds candidate contents and locks grouping/ids, including custom Judge directories. Changed grouping requires a new Cole run; preflight refresh and pending Judge resume retain the same candidates. Historical inputs require explicit --allow-legacy-candidates and are marked as lacking semantic deduplication.

2. Launch one independent Judge per manifest candidate using the host's native subagent tool, in waves respecting its actual concurrency limit (manifest upper limit 6). Each reads bundle.md first, then exact source and relevant indexed tests/docs/config/dependencies. It writes judge.json and judge.md according to references/report-format.md.
3. Complete only sufficiently evidenced classifications. Use needs_context without severity when a necessary fact is missing. Do not force classification because a build failed or another agent agreed.
4. Validate and merge:

```bash
python3 "$SKILL_DIR/scripts/anchor_cole.py" validate-judges <judges/manifest.json>
python3 "$SKILL_DIR/scripts/anchor_cole.py" apply-judges <candidates.json>
python3 "$SKILL_DIR/scripts/anchor_cole.py" validate-results <results.json> --candidates <candidates.json>
```

Malformed outputs block merging; valid pending reviews merge separately. Restore exact candidate provenance when resuming one Judge with new evidence, then apply again. render-report regenerates wreport.md from validated results.

## On-demand execution

Only if a candidate needs an execution test, read references/poc-policy.md and run preflight before writing/running a PoC:

```bash
python3 "$SKILL_DIR/scripts/anchor_cole.py" preflight <project-root> --run <anchor-kai-run>
```

Use --build-command only for a known existing custom project build; --skip-local-build explicitly keeps source-only mode. Preflight records build and test-framework readiness. Missing tools, build failures or no configured existing harness are validation blockers, not automatic Invalid verdicts. Continue source-sufficient reviews. Do not install a target toolchain, change target contracts, create a sandbox or execute against live deployments as part of this skill.

Refresh Judge bundles after changed preflight/evidence. Preserve actual executed PoC paths/commands; classification does not rename test files or imply a rerun. Reports include versions, assumptions, evidence limits and exact execution results.

## References

- references/semantic-dedup.md: parent global grouping, decision contract, provenance and dispatch lock.
- references/triage-policy.md: claim types, severity and pending evidence.
- references/judge-rubric.md: Anchor-specific independent validation.
- references/report-format.md: complete/pending schema 2.0.0.
- references/poc-policy.md: existing harness selection and execution evidence.
