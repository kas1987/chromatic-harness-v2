# Windows Compatibility Fix Patterns

Concrete sed/manual replacement patterns for each incompatible pattern.

---

## Pattern: brew install

**Detection:**
```bash
grep -rn "brew install" ~/.agents/skills/*/SKILL.md
```

**Fixes by package type:**

| Package | brew install | Windows replacement |
|---------|-------------|---------------------|
| jq | `brew install jq` | `winget install jqlang.jq` |
| Python packages | `brew install <pkg>` | `pip install <pkg>` |
| Go tools | `brew install <go-tool>` | `go install <module>@latest` |
| Node tools | `brew install node` | `winget install OpenJS.NodeJS` |
| Git | `brew install git` | `winget install Git.Git` |
| GitHub CLI | `brew install gh` | `winget install GitHub.cli` |
| ripgrep | `brew install ripgrep` | `winget install BurntSushi.ripgrep.MSVC` |
| shellcheck | `brew install shellcheck` | `winget install koalaman.shellcheck` |
| bd CLI | `brew install bd` | Check `~/.agents/tools/` for local binary |
| ao CLI | `brew install ao` | Check `~/.agents/tools/` for local binary |

**Automated fix (safe ones only):**
```bash
# Fix jq
sed -i 's/brew install jq/winget install jqlang.jq/g' ~/.agents/skills/*/SKILL.md

# Fix gh
sed -i 's/brew install gh/winget install GitHub.cli/g' ~/.agents/skills/*/SKILL.md
```

---

## Pattern: find -mtime

**Detection:**
```bash
grep -rn "find.*-mtime" ~/.agents/skills/*/SKILL.md
```

**Fix template:**
```bash
# Replace:
find .agents/learnings/ -mtime -7 2>/dev/null | wc -l

# With:
git log --since="7 days ago" --name-only --format="" -- ".agents/learnings/*.md" 2>/dev/null | grep -v "^$" | wc -l
```

For staleness detection (> N days):
```bash
# Replace: find .agents/ -name "*.md" -mtime +30
# With: filename-based or git log approach:
ls .agents/**/*.md 2>/dev/null | grep -oE "[0-9]{8}" | \
  awk -v cutoff="$(date -d '30 days ago' +%Y%m%d 2>/dev/null || echo '20251219')" '$1 < cutoff' | wc -l
```

---

## Pattern: tmux

**Detection:**
```bash
grep -rn "tmux" ~/.agents/skills/*/SKILL.md
```

**Fix:** Replace distributed swarm tmux references with Windows alternatives.
Point to `skills/swarm/references/windows-mode.md` for the full pattern.

```
# Replace:
tmux new-session -d -s worker-1

# With: (in troubleshooting/notes sections)
# On Windows: use Task(run_in_background=true) for parallel agents
# or spawn-worker.ps1 for process-isolated workers
# See: skills/swarm/references/windows-mode.md
```

---

## Pattern: pbcopy / pbpaste

**Detection:**
```bash
grep -rn "pbcopy\|pbpaste" ~/.agents/skills/*/SKILL.md
```

**Fix:**
```bash
# Replace: cat file.txt | pbcopy
# With:    cat file.txt | clip         (write to clipboard)

# Replace: pbpaste > file.txt
# With:    powershell -command "Get-Clipboard" > file.txt
```

---

## Pattern: /dev/stdin

**Detection:**
```bash
grep -rn "/dev/stdin" ~/.agents/skills/*/SKILL.md
```

**Fix:** Use a temp file or pipe directly instead:
```bash
# Replace: some-command < /dev/stdin
# With:    some-command  (stdin is default anyway)

# Replace: curl ... | process < /dev/stdin
# With:    curl ... > /tmp/data.txt && process < /tmp/data.txt
```

---

## Pattern: open (macOS file opener)

**Detection:**
```bash
grep -rn "\bopen \b" ~/.agents/skills/*/SKILL.md
```

**Fix:**
```bash
# Replace: open file.html
# With:    start file.html   (Git Bash/CMD) or explorer.exe file.html
```

---

## Batch Fix Script

Save as `~/.claude/scripts/fix-windows-compat.sh`:

```bash
#!/bin/bash
# Apply safe automated Windows compatibility fixes to all SKILL.md files

SKILLS_DIR="/c/Users/kas41/.agents/skills"

echo "Applying Windows compatibility fixes..."

# brew install → winget for common packages
sed -i 's/brew install jq/winget install jqlang.jq/g' "$SKILLS_DIR"/*/SKILL.md
sed -i 's/brew install gh/winget install GitHub.cli/g' "$SKILLS_DIR"/*/SKILL.md
sed -i 's/brew install shellcheck/winget install koalaman.shellcheck/g' "$SKILLS_DIR"/*/SKILL.md

# pbcopy → clip
sed -i 's/| pbcopy/| clip/g' "$SKILLS_DIR"/*/SKILL.md

echo "Done. Remaining issues require manual review:"
grep -rn "brew install\|tmux\|pbcopy\|pbpaste\|/dev/stdin" "$SKILLS_DIR"/*/SKILL.md 2>/dev/null | grep -v ".bak"
```

---

## See Also

- `skills/windows-check/SKILL.md` — Scan and report on all issues
- `skills/vibe/references/windows-setup.md` — Installing tools on Windows
- `skills/swarm/references/windows-mode.md` — tmux replacement patterns
