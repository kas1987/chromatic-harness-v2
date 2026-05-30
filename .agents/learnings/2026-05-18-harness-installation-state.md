---
id: research-2026-05-18-harness-installation-state
type: research
date: 2026-05-18
---

# Research: Harness Installation State

**Backend:** inline
**Scope:** Claude Code CLI version, Superpowers plugin version, skills repo state

## Summary

The "Harness" in this setup is the **Superpowers plugin** (v5.1.0, released 2026-04-30) combined with the **custom skills repo** (kas1987/claude-skills). Claude Code CLI is at v2.1.143. The installed Superpowers SHA differs from what the marketplace index currently references, suggesting upstream commits since install — no higher version tag exists yet.

## Key Files

| File | Purpose |
|------|---------|
| `~/.claude/plugins/installed_plugins.json` | Registry of installed plugin versions and SHAs |
| `~/.claude/plugins/cache/claude-plugins-official/superpowers/5.1.0/.claude-plugin/plugin.json` | Installed plugin manifest |
| `~/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json` | Upstream marketplace index |
| `~/.claude/skills/` | Custom skills repo (kas1987/claude-skills) |

## Findings

### Claude Code CLI
- **Version:** 2.1.143
- **State:** Current (installed/updated today)

### Superpowers Plugin (The "Harness")
- **Installed version:** 5.1.0 (released 2026-04-30)
- **Install date:** 2026-01-29, **last refreshed:** 2026-05-18 (today)
- **Installed SHA:** `a0b9ecce2b25aa7d703138f17650540c2e8b2cde`
- **Marketplace SHA:** `f2cbfbefebbfef77321e4c9abc9e949826bea9d7`
- **SHA mismatch** — marketplace has newer commits since the 5.1.0 tag; no v5.2.x tag exists yet
- **Cached versions on disk:** 5.0.7, 5.1.0

### Custom Skills Repo (kas1987/claude-skills)
- **Remote:** https://github.com/kas1987/claude-skills.git
- **State:** Up to date (pulled successfully today)
- **Latest commit:** `37295dc` — hook-audit BATS test suite

### claude-config Repo (~/.claude)
- **Remote:** https://github.com/kas1987/claude-config.git
- **State:** Pulled today — 3 new nightly learning files

## Recommendations

1. **Run `plugin update superpowers`** — the marketplace SHA is ahead of what's installed. This will pull the latest commits (still labeled 5.1.0 until a new tag drops).
2. **Monitor for v5.2.0** — next version likely coming; RELEASE-NOTES shows active development.
3. **Fix claude-powerline** — has uncommitted local changes blocking pulls (separate issue).
