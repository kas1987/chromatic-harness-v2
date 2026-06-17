# Commit and PR Plan — Command Prompt Pack + Console Theme Wave

**Branch:** `chore/harness-cleanup-retention`
**Plan date:** 2026-06-16
**Status:** PLAN ONLY — no git commands have been run. Push/PR is NEEDS-APPROVAL.

---

## (a) Files to Stage — This Session Only

The following files are the SOLE output of this session's wave. All other dirty
files in `.agents/`, `.beads/`, `.github/workflows/`, `02_RUNTIME/runtime-engines/roach-pi`,
and any other pre-existing unrelated edits MUST NOT be staged.

### New files

```
08_PDRS/PDR_COMMAND_PROMPT_SYSTEM.md
08_PDRS/PDR_OPERATOR_COMMAND_PROMPT.md
08_PDRS/PDR_AUDITOR_COMMAND_PROMPT.md
08_PDRS/PDR_DESIGNER_COMMAND_PROMPT.md
04_PLAYBOOKS/COMMAND_PROMPT_SYSTEM_PLAYBOOK.md
scripts/validate_command_prompt_pack.py
scripts/generate_console_themes.py
05_FRONTEND_CONSOLE/src/lib/themes.generated.ts
05_FRONTEND_CONSOLE/src/lib/theme.tsx
05_FRONTEND_CONSOLE/src/components/ThemeSwitcher.tsx
docs/design/COMMIT_AND_PR_PLAN.md
```

Plus this wave's sibling-component edits and new docs (include all sibling files
modified within this session — see the modified list below).

### Modified files

```
01_PROTOCOLS/_schema_registry.yaml
05_FRONTEND_CONSOLE/src/app/layout.tsx
05_FRONTEND_CONSOLE/src/app/page.tsx
docs/pdr/PDR_COMMAND_PROMPT_SYSTEM.md
docs/pdr/PDR_OPERATOR_COMMAND_PROMPT.md
docs/pdr/PDR_AUDITOR_COMMAND_PROMPT.md
docs/pdr/PDR_DESIGNER_COMMAND_PROMPT.md
docs/playbooks/COMMAND_PROMPT_SYSTEM_PLAYBOOK.md
```

> Stub filenames confirmed on disk (2026-06-16). Do NOT use wildcard expansion
> in the actual git add command — each path is listed explicitly above.

---

## (b) Exact `git add` Command (explicit paths, never `-A`)

```sh
git add \
  08_PDRS/PDR_COMMAND_PROMPT_SYSTEM.md \
  08_PDRS/PDR_OPERATOR_COMMAND_PROMPT.md \
  08_PDRS/PDR_AUDITOR_COMMAND_PROMPT.md \
  08_PDRS/PDR_DESIGNER_COMMAND_PROMPT.md \
  04_PLAYBOOKS/COMMAND_PROMPT_SYSTEM_PLAYBOOK.md \
  scripts/validate_command_prompt_pack.py \
  scripts/generate_console_themes.py \
  05_FRONTEND_CONSOLE/src/lib/themes.generated.ts \
  05_FRONTEND_CONSOLE/src/lib/theme.tsx \
  05_FRONTEND_CONSOLE/src/components/ThemeSwitcher.tsx \
  01_PROTOCOLS/_schema_registry.yaml \
  05_FRONTEND_CONSOLE/src/app/layout.tsx \
  05_FRONTEND_CONSOLE/src/app/page.tsx \
  docs/pdr/PDR_COMMAND_PROMPT_SYSTEM.md \
  docs/pdr/PDR_OPERATOR_COMMAND_PROMPT.md \
  docs/pdr/PDR_AUDITOR_COMMAND_PROMPT.md \
  docs/pdr/PDR_DESIGNER_COMMAND_PROMPT.md \
  docs/playbooks/COMMAND_PROMPT_SYSTEM_PLAYBOOK.md \
  docs/design/COMMIT_AND_PR_PLAN.md
```

NEVER run `git add -A`, `git add .`, or `git add *`. Each path must be
individually verified before staging. Run `git status --short` first to
confirm the actual dirty-file list matches what is expected.

---

## (c) Suggested Branch Name and Grouped Commits

### New session branch name

```
feat/command-prompt-pack-and-console-themes
```

Rationale: the current branch `chore/harness-cleanup-retention` is polluted
with unrelated dirty files. A clean branch created from HEAD (before any of
those unrelated files were modified, or from main) isolates this session's
work cleanly. Creating the branch is NEEDS-APPROVAL — do not run this
without explicit user sign-off.

```sh
# NEEDS-APPROVAL before running:
git checkout -b feat/command-prompt-pack-and-console-themes
```

### Commit 1 — frontend + scripts

**Conventional commit:**

```
feat(console): theme runtime + command-center header
```

**Files in this commit:**

```
scripts/generate_console_themes.py
05_FRONTEND_CONSOLE/src/lib/themes.generated.ts
05_FRONTEND_CONSOLE/src/lib/theme.tsx
05_FRONTEND_CONSOLE/src/components/ThemeSwitcher.tsx
05_FRONTEND_CONSOLE/src/app/layout.tsx
05_FRONTEND_CONSOLE/src/app/page.tsx
scripts/validate_command_prompt_pack.py
```

**Full message body:**

```
feat(console): theme runtime + command-center header

Add generate_console_themes.py script that emits themes.generated.ts
from a single source of truth. Wire ThemeSwitcher component into layout
and update page.tsx command-center header to use the new theme context.
Add validate_command_prompt_pack.py as a CI-ready pack integrity check.
```

### Commit 2 — PDRs, playbook, schema, docs

**Conventional commit:**

```
chore(pdr): canonicalize command-prompt pack into taxonomy
```

**Files in this commit:**

```
08_PDRS/PDR_COMMAND_PROMPT_SYSTEM.md
08_PDRS/PDR_OPERATOR_COMMAND_PROMPT.md
08_PDRS/PDR_AUDITOR_COMMAND_PROMPT.md
08_PDRS/PDR_DESIGNER_COMMAND_PROMPT.md
04_PLAYBOOKS/COMMAND_PROMPT_SYSTEM_PLAYBOOK.md
01_PROTOCOLS/_schema_registry.yaml
docs/pdr/PDR_COMMAND_PROMPT_SYSTEM.md
docs/pdr/PDR_OPERATOR_COMMAND_PROMPT.md
docs/pdr/PDR_AUDITOR_COMMAND_PROMPT.md
docs/pdr/PDR_DESIGNER_COMMAND_PROMPT.md
docs/playbooks/COMMAND_PROMPT_SYSTEM_PLAYBOOK.md
docs/design/COMMIT_AND_PR_PLAN.md
```

**Full message body:**

```
chore(pdr): canonicalize command-prompt pack into taxonomy

Add four PDRs covering the command-prompt system and per-role prompt
variants (operator, auditor, designer). Register them in the schema
registry under 01_PROTOCOLS/_schema_registry.yaml. Add the matching
playbook under 04_PLAYBOOKS. Stub PDR and playbook docs entries under
docs/pdr/ and docs/playbooks/. Add commit/PR plan doc under docs/design/.
```

---

## (d) PR Title and Body

### Title

```
feat: command-prompt pack + console theme runtime
```

### Body

```markdown
## Summary

- Introduces a four-PDR command-prompt taxonomy (system, operator, auditor,
  designer) registered in the schema registry and backed by a CI validation
  script.
- Adds a theme-generation pipeline (`generate_console_themes.py` →
  `themes.generated.ts`) with a live `ThemeSwitcher` component wired into
  the console layout.
- Adds the `COMMAND_PROMPT_SYSTEM_PLAYBOOK.md` for operator runbook coverage.
- Stubs the `docs/pdr/` and `docs/playbooks/` catalogue entries to keep the
  docs index current.
- Includes `COMMIT_AND_PR_PLAN.md` as a session audit artifact.

## Scope boundary

Pre-existing dirty files in `.agents/`, `.beads/`, `.github/workflows/`,
`02_RUNTIME/runtime-engines/roach-pi`, and any other unrelated paths are
**excluded** from this PR.

## Test plan

- [ ] `scripts/validate_command_prompt_pack.py` passes with exit 0 against
      all four PDRs.
- [ ] `scripts/generate_console_themes.py` regenerates `themes.generated.ts`
      deterministically (output is checked in; diff should be empty on rerun).
- [ ] `ThemeSwitcher` renders without TypeScript errors (`tsc --noEmit`).
- [ ] Console layout loads in dev mode with no console errors.
- [ ] Schema registry YAML is valid (`python -c "import yaml; yaml.safe_load(open('01_PROTOCOLS/_schema_registry.yaml'))"`).
- [ ] PDR stubs in `docs/pdr/` are reachable from the docs index.

## Checklist

- [ ] All staged paths verified individually with `git status --short` before
      staging.
- [ ] No secrets, tokens, or `.env` values included.
- [ ] No `git add -A` or `git add .` used.
- [ ] Pre-push hook acknowledgement: hook blocks direct push to `main`/`master`;
      push targets feature branch only.
- [ ] PR creation is NEEDS-APPROVAL — do not push or open PR without explicit
      sign-off.
```

---

## (e) Pre-Push Hook Warning and Approval Gate

The global pre-push hook at `~/.claude/` (Git Bash path:
`/c/Users/kas41/.claude/`) blocks all pushes to `main` and `master`.

**Do not run any of the following without explicit approval:**

```sh
# NEEDS-APPROVAL:
git push -u origin feat/command-prompt-pack-and-console-themes
gh pr create --title "feat: command-prompt pack + console theme runtime" --body "..."
```

Steps requiring approval before execution:

1. Confirming the new branch name is acceptable.
2. Running `git checkout -b feat/command-prompt-pack-and-console-themes`.
3. Running the `git add <explicit paths>` staging command.
4. Creating each commit (message should be pasted into a heredoc per hook convention).
5. Pushing the branch to origin.
6. Opening the PR with `gh pr create`.

No git commands have been run as part of authoring this plan.
