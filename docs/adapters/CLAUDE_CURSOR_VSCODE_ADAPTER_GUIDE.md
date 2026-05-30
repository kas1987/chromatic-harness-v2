# Claude / Cursor / VS Code Adapter Guide

## Goal

Make the visual control plane usable by multiple LLM and IDE environments without creating conflicting rule systems.

## Rule

Adapters are bridges. They are not governance.

## Claude

Use:

- `.claude/CLAUDE.md`
- `.claude/commands/generate-visuals.md`
- `.claude/commands/audit-visual-control-plane.md`

Claude should handle long-form synthesis, PDR maintenance, careful documentation, and audit review.

## Cursor

Use:

- `.cursor/rules/chromatic-visual-control-plane.mdc`

Cursor should handle scoped repo edits, registry updates, generated Mermaid refreshes, and quick IDE-integrated implementation.

## VS Code

Use:

- `.vscode/tasks.json`
- `.vscode/extensions.json`

VS Code should expose repeatable tasks for validation and generation.

## ChatGPT / Codex

Use the PDR, playbook, and handoff templates. For code agents, provide exact files, test commands, confidence score, and stop conditions.

## Minimum model handoff

```markdown
# Handoff: Visual Control Plane Task

## Objective

## Allowed Files

## Forbidden Files

## Required Commands

## Acceptance Criteria

## Stop Conditions
```
