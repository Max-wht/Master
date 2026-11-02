---
name: anchor-jay
description: Map Anchor DeFi instruction/account structures and business semantics before audit research. Use for the first phase of the dedicated Anchor audit pipeline; supports Rust AST source analysis without building the target program.
---

# Anchor Jay

Build a source-backed map, then add the business reasoning a syntax parser cannot supply. This standalone skill does not invoke jay-logic. Native Solana Rust is outside v1.

## Source extraction

Resolve this skill's directory as SKILL_DIR. Use Python 3.11+ with the pinned dependencies in scripts/requirements.txt, installed in a dedicated environment. No Anchor/Solana CLI or target compilation is required.

```bash
python3 "$SKILL_DIR/scripts/anchor_jay.py" build <project-root>
python3 "$SKILL_DIR/scripts/anchor_jay.py" build <project-root> --files programs/vault/src/lib.rs
```

Default output: MasterWu/Anchor/Jay/. Explicit files seed the local module/path-dependency closure. Read references/extraction.md for scope, limits and version-sensitive account checks.

## AI business map

Read jay-logic.json, relevant full source, coverage gaps, Cargo manifests/lockfiles and tests/docs. Complete audit-map.json using references/business-map.md:

- Explain user guarantees, account/authority relationships, asset flows, lifecycle/state transitions, coupled-state invariants and external assumptions.
- Associate conclusions with exact source ranges and existing node ids; distinguish source-fact, inference and unresolved. Client deployment statements are evidence to verify.
- Read unresolved helpers/macros/manual constraints. Unextracted controls are unknown, not absent.
- Trace initialization/deposit/settlement/withdrawal/close/recovery together.
- Edit only audit-map.json; preserve graph_digest and AST facts. Mark review_status complete and describe inspected scope/limitations in completion_notes. Mapping completion may retain explicitly unresolved facts.

```bash
python3 "$SKILL_DIR/scripts/anchor_jay.py" validate <project-root>/MasterWu/Anchor/Jay/jay-logic.json --require-semantics
```

Then continue with $anchor-kai. An unchanged rebuild preserves semantics; a changed graph archives the previous map and requires fresh review.

## References

- references/extraction.md: AST facts, implicit checks and coverage gaps.
- references/business-map.md: graph and semantic contracts.
