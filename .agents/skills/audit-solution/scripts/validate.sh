#!/usr/bin/env bash
# Automatically generated MVS compliance validator for skill

SKILL_DIR="$(dirname "$(dirname "$0")")"
MD="$SKILL_DIR/SKILL.md"

if [ ! -f "$MD" ]; then
  echo "SKILL.md not found!"
  exit 1
fi

# Check required sections
grep -q "## Examples" "$MD" || { echo "Missing ## Examples"; exit 1; }
grep -q "## Troubleshooting" "$MD" || { echo "Missing ## Troubleshooting"; exit 1; }
grep -q "## See Also" "$MD" || { echo "Missing ## See Also"; exit 1; }

echo "Skill is MVS compliant!"
exit 0
