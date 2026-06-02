# Governance Register

| Gate | Rule | Enforced By |
|---|---|---|
| Source-of-truth | Queue is the work source, not random PR scraping | Review Dispatch Playbook |
| Evidence | Finding must link to PR/comment/check evidence | review_finding schema |
| Confidence | Mutation requires sufficient confidence | classifier + queue status |
| Scope | Allowed files define patch boundary | mission packet |
| Collision | One mutating agent per PR branch | lock_pr_branch.py |
| Validation | Fix requires checks or documented block | Review Resolution Playbook |
| Human gate | Security/architecture may require approval | classifier + playbooks |
