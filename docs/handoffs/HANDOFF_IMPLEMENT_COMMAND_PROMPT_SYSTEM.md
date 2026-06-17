# Agent Handoff: Implement Command Prompt System

## Role
You are a frontend/runtime integration agent for Chromatic Harness.

## Objective
Add the Command Prompt System pack to `kas1987/chromatic-harness-v2` without breaking the existing visual control plane.

## Context
The repo already contains a Visual Control Plane PDR, schemas, visual registry, and Mermaid generator. This package adds three prompt modes: Operator, Auditor, Designer.

## Instructions
1. Add PDRs under `docs/pdr/`.
2. Add prompt templates under `docs/prompts/`.
3. Add the playbook under `docs/playbooks/`.
4. Add schemas under `schemas/`.
5. Add asset packs under `assets/prompt_variants/`.
6. Update README with a small section pointing to the Command Prompt System.
7. Do not remove existing files.
8. Do not change governance hierarchy.

## Acceptance Criteria
- Files are added in the expected locations.
- README references the prompt system.
- Existing visual control plane remains intact.
- No prompt mode claims authority over CMP or CHROMATIC_TREES.

## Stop Conditions
Stop if root governance files are missing and task requires governance mutation.
