# Mutation Manifest Governance

## Purpose
A mutation manifest forces agents to declare intent before changing files or state.

## Required Before
- Editing files.
- Updating queue state.
- Writing memory.
- Creating migration artifacts.
- Modifying routing logs.
- Changing governance docs.

## Manifest Sections

| Section | Purpose |
|---|---|
| Objective | What the mutation will accomplish |
| Scope | Files/resources allowed |
| Forbidden Scope | Files/resources explicitly excluded |
| Risk Tier | T0-T4 |
| Confidence | 0-100 score before action |
| Rollback Plan | How to undo changes |
| Validation Plan | Tests/checks to run |
| Verifier Required | Whether independent review is required |

## Risk Tier Rules

| Tier | Meaning | Verifier Required |
|---|---|---:|
| T0 | Docs/readme-only minor changes | No |
| T1 | Low-risk docs/config changes | No |
| T2 | Reversible implementation changes | Recommended |
| T3 | Harness behavior/state mutation | Yes |
| T4 | Security, secrets, destructive, infra | Human gate + verifier |

## Stop Conditions
The agent must stop if:

- Scope is unclear.
- Lease is denied.
- Confidence is below 60.
- Resource is already claimed.
- Validation cannot run.
- Human gate is required.
