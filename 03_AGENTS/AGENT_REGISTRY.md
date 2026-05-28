# Agent Registry

| Agent | Role | Default Autonomy | Notes |
|---|---|---:|---|
| Agent Lead | Synthesis, final findings, next actions | L1-L3 | Does not perform main work |
| Scout | Context discovery | L0-L1 | Read/search only |
| Builder | Scoped implementation | L2-L3 | Patch only assigned files |
| Auditor | Review and verification | L1-L3 | Tests, diffs, evidence |
| Scribe | State/docs/log updates | L1-L2 | Keeps source of truth current |
| Reviewer | Independent critique | L0-L1 | No mutation |
| Security | Risk/injection/secrets review | L0-L2 | Can trigger halt |
