# Lease Ledger Governance

## Purpose
The lease ledger is the source of truth for active autonomous mutation ownership.

## Rule
No agent may mutate state unless it owns an active, non-expired lease covering the target resource.

## Lease Fields

| Field | Required | Description |
|---|---:|---|
| `lease_id` | Yes | Unique lease identifier |
| `task_id` | Yes | Queue item, issue, or mission ID |
| `owner_agent` | Yes | Agent claiming the lease |
| `resources` | Yes | Files, directories, queue items, issues, or state resources |
| `mode` | Yes | `read`, `write`, `exclusive`, or `verify` |
| `risk_tier` | Yes | T0-T4 |
| `expires_at` | Yes | TTL expiration timestamp |
| `heartbeat_at` | Recommended | Last active heartbeat |
| `rollback_plan` | Yes for write | How to undo mutation |
| `status` | Yes | `active`, `released`, `expired`, `revoked`, `failed` |

## Collision Rule
A new write/exclusive lease is rejected if it overlaps any active write/exclusive lease.

## TTL Defaults

| Risk Tier | Default TTL |
|---|---:|
| T0 | 15 minutes |
| T1 | 30 minutes |
| T2 | 60 minutes |
| T3 | 90 minutes |
| T4 | Human approval required |

## Emergency Override
Emergency override requires:

1. Reason.
2. Human or verifier approval.
3. Incident record.
4. Follow-up audit.

## Health Dashboard Signals

- Active leases count.
- Stale leases count.
- Longest active lease age.
- Last collision event.
- Failed acquire attempts.
