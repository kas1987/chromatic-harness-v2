# Playbook Index & Coverage Audit (OMH-9)

Bead: `chromatic-harness-v2-w1bf.9` — *Playbook-coverage audit + index*.
Epic: `chromatic-harness-v2-w1bf` — Operating-Model Hardening (OMH).

Every operating level should have **at least one** playbook. This index maps the eight
levels of the operating model onto their playbook(s) and is the audit of record for
coverage. Playbooks live in two roots: `docs/playbooks/` (protocols/runbooks) and
`04_PLAYBOOKS/` (subsystem playbooks).

## Coverage by operating level

| Level | Playbook(s) | Root | Status |
|-------|-------------|------|--------|
| **author** | [BEAD_EPIC_AUTHORING_PROTOCOL.md](BEAD_EPIC_AUTHORING_PROTOCOL.md); `BEADS_PLAYBOOK.md` | both | ✅ |
| **dispatch** | [DISPATCH_PLAYBOOK.md](DISPATCH_PLAYBOOK.md); `REVIEW_DISPATCH_PLAYBOOK.md` | both | ✅ |
| **collision** | [COLLISION_RESPONSE_PLAYBOOK.md](COLLISION_RESPONSE_PLAYBOOK.md), [LEASE_PLAYBOOK.md](LEASE_PLAYBOOK.md); `PR_COLLISION_CONTROL_PLAYBOOK.md` | both | ✅ |
| **review** | `REVIEW_INTAKE_PLAYBOOK.md`, `REVIEW_RESOLUTION_PLAYBOOK.md` | `04_PLAYBOOKS/` | ✅ |
| **learn** | `REVIEW_LEARNING_PLAYBOOK.md` | `04_PLAYBOOKS/` | ✅ |
| **route** | `MODEL_ROUTING_PLAYBOOK.md` | `04_PLAYBOOKS/` | ✅ |
| **loop** | [GO_MODE_PLAYBOOK.md](GO_MODE_PLAYBOOK.md) | both | ✅ |
| **promote** | [PROMOTE_PLAYBOOK.md](PROMOTE_PLAYBOOK.md) | `docs/playbooks/` | ✅ *(filled by OMH-9)* |

All eight levels now have ≥ 1 playbook. The **promote** level was the only hole at audit
time (covered only by reference docs, not a runbook); OMH-9 added
[PROMOTE_PLAYBOOK.md](PROMOTE_PLAYBOOK.md).

## Supporting playbooks (cross-level)

| Playbook | Root | Covers |
|----------|------|--------|
| [CONFIDENCE_GATE_PLAYBOOK.md](CONFIDENCE_GATE_PLAYBOOK.md) | `docs/playbooks/` | confidence-gated auto-merge |
| [ORCHESTRATOR_PLAYBOOK.md](ORCHESTRATOR_PLAYBOOK.md) | both | multi-agent orchestration |
| [AUTONOMOUS_RECOVERY_PLAYBOOK.md](AUTONOMOUS_RECOVERY_PLAYBOOK.md) | `docs/playbooks/` | post-failure recovery |
| [VISUAL_CONTROL_PLANE_PLAYBOOK.md](VISUAL_CONTROL_PLANE_PLAYBOOK.md) | `docs/playbooks/` | visual control plane |
| `AGENT_ONBOARDING_PLAYBOOK.md` | `04_PLAYBOOKS/` | agent onboarding |
| `MAGNETS_PLAYBOOK.md` | `04_PLAYBOOKS/` | magnets pipeline |
| `SANDBOX_LAB_PLAYBOOK.md` | `04_PLAYBOOKS/` | sandbox experiments |
| `SESSION_COMPACT_PLAYBOOK.md` | `04_PLAYBOOKS/` | session compaction |
| `WORKFLOWS_PLAYBOOK.md` | `04_PLAYBOOKS/` | lite workflows |

## Maintenance

When a new operating level or subsystem is added, add its playbook and a row here.
Re-audit on the same cadence as the skill-profile audit
([SKILL_PROFILES.md](../governance/SKILL_PROFILES.md)) — the level names are shared, so a
gap in one usually signals a gap in the other.
