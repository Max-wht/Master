# MasterWu Skill Repository

MasterWu is the parent repository for local audit skills. Each skill is a standalone bundle under `skills/`. The core audit pipeline is `jay-logic -> kai-research -> cole-varify` and supports Solidity, Move, and Anchor/Solana runtime profiles.

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
