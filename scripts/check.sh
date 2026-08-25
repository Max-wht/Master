#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_FILTER="${1:-all}"
PYTHON="${PYTHON:-python3}"
VALIDATOR="${SKILL_VALIDATOR:-${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if ! "$PYTHON" - <<'PY' >/dev/null 2>&1
import yaml
PY
then
  VENV="$ROOT/.venv-check"
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/python" -m pip install -q --disable-pip-version-check PyYAML
  PYTHON="$VENV/bin/python"
fi

export PYTHONPYCACHEPREFIX="$TMP/pycache"

if [[ ! -f "$VALIDATOR" ]]; then
  echo "Missing skill validator: $VALIDATOR" >&2
  exit 1
fi

selected_skill_dirs() {
  if [[ "$SKILL_FILTER" == "all" ]]; then
    local skill_dir
    for skill_dir in "$ROOT"/skills/*; do
      [[ -f "$skill_dir/SKILL.md" ]] || continue
      echo "$skill_dir"
    done
    return
  fi
  if [[ ! -f "$ROOT/skills/$SKILL_FILTER/SKILL.md" ]]; then
    echo "Unknown skill: $SKILL_FILTER" >&2
    exit 2
  fi
  echo "$ROOT/skills/$SKILL_FILTER"
}

compile_skill_python() {
  local skill_dir="$1"
  [[ -d "$skill_dir/scripts" ]] || return 0
  local py_files=()
  while IFS= read -r py_file; do
    py_files+=("$py_file")
  done < <(find "$skill_dir/scripts" -type f -name '*.py' | sort)
  [[ "${#py_files[@]}" -eq 0 ]] || "$PYTHON" -m py_compile "${py_files[@]}"
}

check_jay_logic() {
  local skill_dir="$1"
  local name
  name="$(basename "$skill_dir")"
  [[ "$name" == "jay-logic" ]] || return 0
  [[ -f "$skill_dir/scripts/jay_logic.py" ]] || return 0

  "$PYTHON" "$skill_dir/scripts/jay_logic.py" build "$ROOT/tests/fixtures/solidity" --out "$TMP/solidity" --lang solidity
  "$PYTHON" "$skill_dir/scripts/jay_logic.py" validate "$TMP/solidity/jay-logic.json"
  "$PYTHON" "$skill_dir/scripts/jay_logic.py" build "$ROOT/tests/fixtures/move" --out "$TMP/move" --lang move
  "$PYTHON" "$skill_dir/scripts/jay_logic.py" validate "$TMP/move/jay-logic.json"
  "$PYTHON" "$skill_dir/scripts/jay_logic.py" build "$ROOT/tests/fixtures/anchor" --out "$TMP/anchor" --lang anchor
  "$PYTHON" "$skill_dir/scripts/jay_logic.py" validate "$TMP/anchor/jay-logic.json"
  "$PYTHON" "$ROOT/tests/test_jay_logic.py" "$TMP/solidity/jay-logic.json" "$TMP/move/jay-logic.json" "$TMP/anchor/jay-logic.json"
}

check_kai_research() {
  local skill_dir="$1"
  local name
  name="$(basename "$skill_dir")"
  [[ "$name" == "kai-research" ]] || return 0
  [[ -f "$skill_dir/scripts/kai_prepare.py" ]] || return 0

  local project="$TMP/kai-project"
  mkdir -p "$project"
  cp -R "$ROOT/tests/fixtures/solidity/." "$project/"

  "$PYTHON" "$skill_dir/scripts/kai_prepare.py" prepare "$project" --run-id check-kai
  "$PYTHON" "$skill_dir/scripts/kai_prepare.py" prepare "$project" --run-id check-kai-explicit --files lib/ExplicitLibrary.sol
  local move_project="$TMP/kai-move-project"
  mkdir -p "$move_project"
  cp -R "$ROOT/tests/fixtures/move/." "$move_project/"
  "$PYTHON" "$skill_dir/scripts/kai_prepare.py" prepare "$move_project" --lang move --run-id check-kai-move
  local anchor_project="$TMP/kai-anchor-project"
  mkdir -p "$anchor_project"
  cp -R "$ROOT/tests/fixtures/anchor/." "$anchor_project/"
  "$PYTHON" "$skill_dir/scripts/kai_prepare.py" prepare "$anchor_project" --lang anchor --run-id check-kai-anchor
  local mixed_project="$TMP/kai-mixed-project"
  mkdir -p "$mixed_project"
  cp -R "$ROOT/tests/fixtures/solidity/." "$mixed_project/"
  mkdir -p "$mixed_project/sources"
  cp "$ROOT/tests/fixtures/move/sources/vault.move" "$mixed_project/sources/vault.move"
  if "$PYTHON" "$skill_dir/scripts/kai_prepare.py" prepare "$mixed_project" --run-id check-kai-mixed >/dev/null 2>&1; then
    echo "Kai prepare should fail on mixed runtimes when --lang is not set" >&2
    exit 1
  fi
  if "$PYTHON" "$skill_dir/scripts/kai_prepare.py" prepare "$project" --run-id check-kai-missing --jay-skill-dir "$TMP/missing-jay" >/dev/null 2>&1; then
    echo "Kai prepare should fail when Jay is missing" >&2
    exit 1
  fi
  "$PYTHON" "$ROOT/tests/test_kai_research.py" \
    "$project/MasterWu/Kai/runs/check-kai" \
    "$project/MasterWu/Kai/runs/check-kai-explicit" \
    "$move_project/MasterWu/Kai/runs/check-kai-move" \
    "$anchor_project/MasterWu/Kai/runs/check-kai-anchor"
  "$PYTHON" "$skill_dir/scripts/kai_prepare.py" validate-hypotheses "$project/MasterWu/Kai/runs/check-kai/agents/01-math-precision/hypotheses.json"
}

check_cole_varify() {
  local skill_dir="$1"
  local name
  name="$(basename "$skill_dir")"
  [[ "$name" == "cole-varify" ]] || return 0
  [[ -f "$skill_dir/scripts/cole_varify.py" ]] || return 0

  "$PYTHON" "$ROOT/tests/test_cole_varify.py" "$skill_dir/scripts/cole_varify.py"
}

checked=0
while IFS= read -r skill_dir; do
  echo "Checking $(basename "$skill_dir")"
  compile_skill_python "$skill_dir"
  "$PYTHON" "$VALIDATOR" "$skill_dir"
  check_jay_logic "$skill_dir"
  check_kai_research "$skill_dir"
  check_cole_varify "$skill_dir"
  checked=$((checked + 1))
done < <(selected_skill_dirs)

echo "MasterWu skill checks passed ($checked skill(s))"
