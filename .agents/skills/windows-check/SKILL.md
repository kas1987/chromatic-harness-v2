---
name: windows-check
description: 'Windows compatibility validator. Scans all SKILL.md files for Mac/Linux-only patterns, reports compatibility score per skill, generates fix suggestions. Triggers: "windows check", "check windows compat", "find brew install", "windows compatibility".'
metadata:
  tier: solo
  dependencies: []
---

# Windows-Check Skill

> **Quick Ref:** Scan all skills for Windows-incompatible patterns. Output: per-skill compatibility score + fix suggestions.

**YOU MUST EXECUTE THIS WORKFLOW. Do not just describe it.**

## Incompatible Patterns

| Pattern | Problem | Windows Fix |
|---------|---------|-------------|
| `brew install <pkg>` | macOS package manager | `winget install <pkg>` or `pip install` or `go install` |
| `tmux` | Unix terminal multiplexer | Windows Terminal tabs or PowerShell background jobs |
| `pbcopy` / `pbpaste` | macOS clipboard | `clip` (write) / PowerShell `Get-Clipboard` (read) |
| `find -mtime` | Unreliable on Windows | `git log --since` or filename-based date check |
| `/dev/stdin` | Unix device file | Use temp files or process substitution alternatives |
| `open <file>` | macOS file opener | `start <file>` or `explorer.exe <file>` |
| `#!/usr/bin/env python3` | May not work if Python not aliased | Use `python` in Git Bash or `python3` if explicitly installed |
| `xclip` / `xsel` | Linux clipboard tools | `clip` on Windows |
| `which <cmd>` | Works in Git Bash but not PowerShell | Add PowerShell fallback: `Get-Command <cmd>` |
| `sleep` (sub-second) | `sleep 0.5` not supported in Git Bash | Use `Start-Sleep -Milliseconds 500` in PowerShell |

## Execution Steps

Given `/windows-check [--fix] [skill-name]`:

### Step 1: Discover Skills

```bash
SKILLS_DIR="/c/Users/kas41/.agents/skills"
ls -d "$SKILLS_DIR"/*/SKILL.md 2>/dev/null | sed 's|/SKILL.md||' | xargs -I{} basename {}
```

### Step 2: Scan Each SKILL.md for Incompatible Patterns

```bash
INCOMPATIBLE_PATTERNS="brew install|tmux|pbcopy|pbpaste|find.*-mtime|/dev/stdin|open [a-z]|xclip|xsel"

for skill_dir in "$SKILLS_DIR"/*/; do
  skill=$(basename "$skill_dir")
  md="$skill_dir/SKILL.md"
  [ -f "$md" ] || continue

  hits=$(grep -cE "$INCOMPATIBLE_PATTERNS" "$md" 2>/dev/null || echo 0)
  if [ "$hits" -gt 0 ]; then
    echo "ISSUES ($hits): $skill"
    grep -nE "$INCOMPATIBLE_PATTERNS" "$md" | head -5
  fi
done
```

### Step 3: Compute Compatibility Score

For each skill:
- Start at 100
- Subtract 10 per incompatible pattern instance
- Minimum 0

Output format:
```
skill-name: 100% (no issues)
skill-name: 80% (2 issues: brew install on line 45, tmux on line 87)
skill-name: 60% (4 issues)
```

### Step 4: Generate Fix Suggestions

For each issue found, generate the specific fix:

```bash
grep -n "brew install" "$md" | while IFS=: read linenum content; do
  pkg=$(echo "$content" | grep -oE "brew install [a-zA-Z0-9_-]+" | sed 's/brew install //')
  echo "Line $linenum: Replace 'brew install $pkg' with:"
  case "$pkg" in
    python*|pip*) echo "  pip install $pkg" ;;
    go*) echo "  go install $pkg@latest" ;;
    jq) echo "  winget install jqlang.jq" ;;
    node|nodejs) echo "  winget install OpenJS.NodeJS" ;;
    *) echo "  winget install $pkg  # verify package name at winget.run" ;;
  esac
done
```

### Step 5: Write Compatibility Report

**Write to:** `.agents/audit/YYYYMMDD-windows-compat.md`

```markdown
# Windows Compatibility Report

**Date:** YYYY-MM-DD
**Skills scanned:** N
**Fully compatible:** N (100%)
**Minor issues:** N (80-99%)
**Major issues:** N (<80%)

## Skills with Issues

### brew install (install to replace with winget/pip/go)
- skill-name:L45 — `brew install jq` → `winget install jqlang.jq`

### tmux (replace with Windows Terminal alternatives)
- skill-name:L87 — `tmux new-session` → see swarm/references/windows-mode.md

### find -mtime (replace with git log)
- skill-name:L55 — `find .agents/ -mtime -7` → `git log --since="7 days ago" --name-only`

## Fix Commands

Run these edits to fix all issues:
```bash
sed -i 's/brew install jq/winget install jqlang.jq/g' skills/*/SKILL.md
```
```

### Step 6: Fix Mode (if --fix flag)

Apply automated fixes for safe patterns:

1. `brew install jq` → `winget install jqlang.jq`
2. `find . -name "*.py" -mtime -7` → `git log --since="7 days ago" --name-only -- "*.py"`
3. `pbcopy` → `clip`

Requires review for: `tmux` replacements (context-dependent).

## Examples

### Full Compatibility Scan

**User says:** `/windows-check`

**What happens:**
1. Agent scans all 30 skill SKILL.md files
2. Finds `brew install` in 6 files, `find -mtime` in 2 files, `tmux` in 1 file
3. Computes per-skill scores
4. Writes report with specific line numbers and fix suggestions

**Result:** Report shows 22/30 at 100%, 8 need fixes. Fix commands provided.

---

### Single Skill Check

**User says:** `/windows-check vibe`

**What happens:**
1. Agent checks only `skills/vibe/SKILL.md`
2. Reports any incompatible patterns found

**Result:** Single skill report with line numbers.

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Patterns not detected | grep pattern doesn't match variant | Check exact text with `grep -n "brew" skills/*/SKILL.md` |
| False positives | Pattern matches comment or quoted text | Review manually — "brew install" in a table cell explaining what NOT to do |
| Fix broke formatting | sed replacement changed table alignment | Review the diff; adjust manually if needed |
| Report dir missing | `.agents/audit/` doesn't exist | Run `mkdir -p .agents/audit` |

---

## See Also

- `skills/audit/SKILL.md` — Full MVS compliance checker (superset of this skill)
- `skills/vibe/references/windows-setup.md` — Windows-specific tool installation
- `skills/research/references/windows-notes.md` — Windows development environment notes
- `skills/swarm/references/windows-mode.md` — Windows-compatible parallel agent patterns
