# MasterWu Skill Repository

MasterWu is the parent repository for local audit skills. Each skill is a standalone bundle under `skills/`. The core audit pipeline is `jay-logic -> kai-research -> cole-varify` and supports Solidity, Move, and Anchor/Solana runtime profiles.

The dedicated Anchor DeFi pipeline is `anchor-jay -> anchor-kai -> anchor-cole`.
It uses Rust AST extraction and a separately reviewed AI business map, twelve
Anchor-native research specialists, and source-first private-audit verification.
It does not invoke the original skills. Python 3.11+ and the pinned packages in
`skills/anchor-jay/scripts/requirements.txt` are required; Anchor/Solana CLI is
needed only for on-demand execution validation. The check script provisions an
isolated `.venv-check` for its Python dependencies.

1. Run `anchor-jay` build, complete `audit-map.json` with AI source review, then
   validate with `--require-semantics`.
2. Run `anchor-kai` prepare, complete the twelve specialist tasks and validate
   their hypotheses.
3. Run `anchor-cole` collect, prepare/validate Judges, and apply results. Run
   preflight only when a PoC is needed; missing tools or an existing test harness
   records a blocker while source-sufficient review continues.

Artifacts live under `MasterWu/Anchor/`. No toolchain installation, new test
sandbox, live deployment verification or real-project detection benchmark is
included. Source/contract regression fixtures do not represent measured audit
recall or successful execution of real Anchor programs.

## Tree

```text
MasterWu/
  scripts/
    check.sh
    install.sh
  skills/
    jay-logic/
      SKILL.md
      agents/
      references/
      scripts/
    kai-research/
      SKILL.md
      agents/
      references/
      scripts/
    cole-varify/
      SKILL.md
      agents/
      references/
      scripts/
  tests/
    fixtures/
```

## Skill Bundle Contract

Every installable skill must live at `skills/<skill-name>/` and include:

```text
skills/<skill-name>/
  SKILL.md
```

Optional runtime assets should stay inside that skill directory:

```text
skills/<skill-name>/
  agents/
  references/
  scripts/
  templates/
```

## Commands

Check every skill:

```bash
./scripts/check.sh
```

Check one skill:

```bash
./scripts/check.sh jay-logic
./scripts/check.sh kai-research
./scripts/check.sh cole-varify
```

Install every skill to Codex and Claude:

```bash
./scripts/install.sh all
```

Install one skill to one target:

```bash
./scripts/install.sh codex jay-logic
./scripts/install.sh claude jay-logic
./scripts/install.sh codex kai-research
./scripts/install.sh claude kai-research
./scripts/install.sh codex cole-varify
./scripts/install.sh claude cole-varify
```

The scripts discover skills from `skills/*/SKILL.md`. Jay fixture tests cover Solidity, Move, and Anchor extraction; Kai tests cover runtime-aware bundle preparation and mixed-runtime rejection; Cole tests cover Solidity, Move, Anchor, and skip-build preflight behavior.

Installing `anchor-kai` also installs `anchor-jay`; installing `anchor-cole`
installs all three dedicated Anchor skills. Tests can override installation
destinations with `MASTERWU_CODEX_SKILLS_DIR` and `MASTERWU_CLAUDE_SKILLS_DIR`
without modifying the user's home directories. The existing install defaults
are unchanged. Check the new pipeline with `./scripts/check.sh anchor-jay`,
`anchor-kai`, or `anchor-cole`; the full check covers all six skills.
