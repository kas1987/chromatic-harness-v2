# Chromatic Harness Mission Packs

**Version:** 0.1.0  
**Purpose:** Establish a controlled, repeatable operating model for creating, reviewing, approving, implementing, validating, and closing Mission Packs across Chromatic Harness v2.

## Executive Summary

Mission Packs are the execution unit of Chromatic Harness. Every meaningful change should be classified as **M1 Basic**, **M2 Intermediate**, **M3 Complex**, or **M4 Atomic** before work begins. The level determines planning depth, governance rigor, review requirements, validation expectations, and whether a formal PDR is required.

This package gives the Harness a deployable framework for:

1. Creating right-sized Mission Packs.
2. Scoring complexity, risk, confidence, reversibility, and governance level.
3. Reviewing missions before implementation.
4. Dispatching agents or subagents with bounded scope.
5. Validating work before closeout.
6. Logging lessons learned so the Harness improves over time.

## Core Principle

> **Right mission. Right complexity. Right process. Right governance.**

The goal is not maximum paperwork. The goal is the minimum sufficient rigor needed to prevent drift, tool waste, bad merges, shallow validation, and uncontrolled autonomous execution.

## Recommended Repo Placement

```text
/MISSIONS/
  README.md
  PDR_MISSION_PACKS_GOVERNANCE.md
  INSTRUCTIONS_MISSION_PACK_OPERATING_MODEL.md
  BEADS.md
  /templates/
  /playbooks/
  /schemas/
  /beads/
  /checklists/
  /examples/
  /logs/
```

## How to Use

### 1. Intake the work

Capture the requested objective in a Mission Intake. Do not let an agent start work from a vague command like `GO` unless it can resolve the next task from the queue and produce a valid Mission Packet.

### 2. Classify the mission

Use the complexity rules:

| Level | Use When | Governance |
|---|---|---|
| M1 Basic | Simple, low-risk, small scoped change | Standard |
| M2 Intermediate | Moderate complexity, dependencies, multiple steps | Elevated |
| M3 Complex | Multi-system, high-risk, cross-cutting change | High |
| M4 Atomic | Critical, irreversible, architecture/security/production impact | Maximum |

### 3. Select the template

Use the matching YAML template from `/templates/`.

### 4. Review before implementation

No M2+ mission should begin without at least a lightweight review. M3 and M4 require structured review and explicit validation strategy.

### 5. Execute with bounded autonomy

Agents must only work inside the Mission Packet boundaries: allowed files, forbidden files, tools, budget, stop conditions, validation requirements, and definition of done.

### 6. Validate and close

Every mission closes with evidence: files touched, tests run, acceptance criteria result, risk changes, logs updated, and next recommended task.

## Files Included

| File | Purpose |
|---|---|
| `PDR_MISSION_PACKS_GOVERNANCE.md` | Main planning and design record |
| `INSTRUCTIONS_MISSION_PACK_OPERATING_MODEL.md` | Operational instructions for humans and agents |
| `BEADS.md` | BEAD system for atomic execution units |
| `templates/*.yaml` | M1-M4 mission templates |
| `playbooks/*.md` | Execution and review playbooks |
| `schemas/*.json` | Machine-readable validation schemas |
| `checklists/*.md` | Review, implementation, validation, and closeout checklists |
| `scripts/validate_mission_packet.py` | Basic YAML mission validator |
| `examples/*.yaml` | Example mission packets |
| `reference/mission_packet_m1_m4.png` | Source visual reference |

## Non-Negotiables

- No dispatch without a Mission Packet.
- No mutation below the confidence threshold.
- No M3/M4 without rollback and validation strategy.
- No M4 without formal approval.
- No closeout without evidence.
- No repeated rediscovery when logs already exist.

