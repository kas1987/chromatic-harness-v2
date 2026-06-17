# Mission Complexity Matrix

| Dimension | M1 Basic | M2 Intermediate | M3 Complex | M4 Atomic |
|---|---|---|---|---|
| Risk | Low | Moderate | High | Critical |
| Scope | Single small area | Multiple steps or moderate area | Multiple systems | Architecture/security/production/data impact |
| Planning | Simple steps | Step list | Detailed plan | Comprehensive plan |
| PDR | No | Light | Yes | Full |
| Review | Optional | 1 reviewer | 2+ reviewers | 3+ reviewers + council |
| Validation | Basic | Standard | Comprehensive | Exhaustive |
| Rollback | N/A | Basic | Detailed | Full proof |
| Approval | No | Yes | Yes | Formal |
| Examples | Docs update, config tweak, add test | Feature with tests, API endpoint, DB migration | Major feature, system integration, security improvement | Core architecture, data model overhaul, production rollout |

## Escalation Rule

When uncertain, do not automatically choose the largest level. Instead ask:

1. Can this break production or shared architecture?
2. Can this expose secrets or user data?
3. Can this cause data loss?
4. Is rollback unclear?
5. Does this affect multiple systems or teams?
6. Would failure require incident response?

If yes to 1-3, consider M4. If yes to 4-6, consider M3.
