#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-all}"
SKILL_FILTER="${2:-all}"

usage() {
  echo "Usage: $0 [codex|claude|all] [skill-name|all]" >&2
}

skill_names() {
  local found=0
  local skill_dir
  for skill_dir in "$ROOT"/skills/*; do
    [[ -f "$skill_dir/SKILL.md" ]] || continue
    basename "$skill_dir"
    found=1
  done
  [[ "$found" -eq 1 ]]
}

selected_skill_names() {
  if [[ "$SKILL_FILTER" == "all" ]]; then
    skill_names
    return
  fi
  if [[ ! -f "$ROOT/skills/$SKILL_FILTER/SKILL.md" ]]; then
    echo "Unknown skill: $SKILL_FILTER" >&2
    exit 2
  fi
  echo "$SKILL_FILTER"
}

install_skills() {
  local dest="$1"
  mkdir -p "$dest"
  local skill
  while IFS= read -r skill; do
    rsync -a --delete \
      --exclude '__pycache__/' \
      --exclude '*.pyc' \
      "$ROOT/skills/$skill/" "$dest/$skill/"
    diff -qr "$ROOT/skills/$skill" "$dest/$skill" \
      -x '__pycache__' -x '*.pyc' >/dev/null
    echo "Installed $skill to $dest/$skill"
  done < <(selected_skill_names)
}

case "$TARGET" in
  codex)
    install_skills "${CODEX_HOME:-$HOME/.codex}/skills"
    ;;
  claude)
    install_skills "$HOME/.claude/skills"
    ;;
  all)
    install_skills "${CODEX_HOME:-$HOME/.codex}/skills"
    install_skills "$HOME/.claude/skills"
    ;;
  *)
    usage
    exit 2
    ;;
esac
