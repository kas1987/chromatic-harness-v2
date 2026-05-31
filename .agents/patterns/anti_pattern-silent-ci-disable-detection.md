---
name: silent-ci-disable-detection
type: anti-pattern
confidence: 0.90
source_learnings: [2026-05-30-silent-ci-disable-detection]
description: GitHub Actions can be disabled at the repo level — and look like it's still running
tags: []
---

# GitHub Actions can be disabled at the repo level — and look like it's still running

## Observation

CI silently stopped running on every branch/PR for ~2 days. The repo still showed
green/active workflows in `gh workflow list`, and "Copilot Code Review" runs kept
appearing on every branch — so at a glance CI looked alive. In fact GitHub **Actions
was disabled at the repo level** (`actions/permissions` → `enabled: false`). The
Copilot runs are a **GitHub App**, not the Actions runner, so they are unaffected by
that toggle and masked the outage.

## Evidence

- `gh api repos/<owner>/<repo>/actions/permissions` → `{"enabled": false, ...}`
- `gh run list --workflow ci.yml` showed the last `ci.yml` run was 2 days stale while
  pushes kept happening; only `Copilot` runs were recent.
- Re-enable: `gh api -X PUT .../actions/permissions -F enabled=true -f allowed_actions=all`.

## Recommendation

- Don't trust "there are recent Actions runs" — a bot App (Copilot/Codex) keeps running
  when Actions is off. Check `actions/permissions.enabled` and the *specific* workflow's
  last-run age.
- Add an on-demand probe (`scripts/gh_ci_health.py`) that flags Actions-disabled or
  failed/stale CI, and wire it into SessionStart or a magnet so the gap self-reports.
- **Cost note:** public repos get *free unlimited* standard-runner minutes (Linux +
  Windows), so cost is not a reason to disable Actions there; per-minute billing only
  applies to private repos (Windows 2×, macOS 10×).
