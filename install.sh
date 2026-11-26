#!/usr/bin/env bash
# Symlink every skill in ./skills into the agent skill directories.
# Usage: ./install.sh [skill-name ...]   (no args = all skills)
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
targets=("$HOME/.agents/skills" "$HOME/.claude/skills" "$HOME/.cursor/skills" "$HOME/.codex/skills")

if [ "$#" -gt 0 ]; then
  skills=("$@")
else
  skills=()
  for d in "$repo"/skills/*/; do skills+=("$(basename "$d")"); done
fi

for skill in "${skills[@]}"; do
  src="$repo/skills/$skill"
  [ -f "$src/SKILL.md" ] || { echo "skip $skill: no SKILL.md" >&2; continue; }
  for t in "${targets[@]}"; do
    mkdir -p "$t"
    dest="$t/$skill"
    if [ -L "$dest" ]; then
      ln -sfn "$src" "$dest"
    elif [ -e "$dest" ]; then
      echo "skip $dest: exists and is not a symlink" >&2
      continue
    else
      ln -s "$src" "$dest"
    fi
    echo "linked $dest -> $src"
  done
done
