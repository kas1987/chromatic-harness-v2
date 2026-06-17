# Gen Infrastructure Foundation Audit

Date: 2026-04-05
Scope: Hooks and process-flow infrastructure in gen
Method: Reverse-engineered review + live diagnostics + independent subagent cross-check

## A. Executive Diagnosis

The foundation is directionally strong in architecture, but currently weak in runtime evidence quality.

Strengths:
- Clear hook separation across user-prompt, pretool, and posttool.
- Good fail-open posture that avoids blocking critical workflows.
- Explicit observability model for routing and reconciliation.

Weaknesses:
- Runtime database state does not currently support the observability model.
- Whole-task delegation surface is implemented but not mounted in active app routes.
- Cost and token economics are under-instrumented in active telemetry.

Decision:
- Treat the current state as Warning and not production-verified for provider-routing economics until P0 items are complete.

## B. Reverse-Engineered Reality

### Core runtime path
1. user prompt enters /hooks/user-prompt, optional hop middleware intercept applies only when metadata.intent_tag exists.
2. pretool evaluates guards and budgets, computes suggested llm, and attempts to append routing telemetry.
3. posttool records outcomes, increments counters where payload provides token counts, and appends reconciliation telemetry.

### Delegation and hop surfaces
- Delegate endpoint exists in code but is not mounted in app route registration.
- Hop middleware dispatches locally/remotely in best-effort mode and always falls through.

## C. Goal and Completeness Review

Weighted score: 2.30 / 5 (Warning)

Dimension highlights:
- Strongest: goal_clarity (4/5)
- Weakest: observability (1/5)
- Overall risk driver: runtime schema and route wiring drift from intended architecture

## D. Knowledge Basis Review

Observed facts:
- Diagnostics run against runtime DB path ./gen.db.
- routing_decisions table absent in active DB.
- task_outcomes has only 1 row and lacks llm attribution columns in active DB.
- delegation_log has 0 rows.
- budget_states has activity on external calls, but tokens/handoffs are zero.

Confidence profile:
- Most top findings are observed from code plus runtime diagnostics.
- Efficiency and economics conclusions include strong inference where payload quality is variable.

## E. Efficiency Review

Current bottlenecks:
- Missing routing_decisions data blocks automated provider-routing optimization.
- Sparse token data blocks budget tuning and model economics governance.
- No durable hop retry path can cause hidden rework during transient failures.

## F. External Best Practice Overlay

Applied principles:
- Startup schema contracts for critical telemetry tables.
- Route-surface parity checks between implemented endpoints and mounted routers.
- Durable asynchronous dispatch with retry and dead-letter replay.
- Low-cardinality telemetry fields with complete attribution for cost/routing analysis.

## G. Priority Recommendations

P0:
1. Mount and initialize delegate router so whole-task offload is actually callable.
2. Add startup schema contract checks and strict fail-fast mode for required observability tables and columns.

P1:
3. Normalize token capture on posttool clients so budget and outcome stores carry non-zero economics data.
4. Add persistent retry/dead-letter replay for hop dispatch path.

P2:
5. Add CI gate using scripts/diagnose_gen_observability.py and fail build on blocking telemetry regressions.

P3:
6. Add weekly architecture audit dashboard driven by routing reconciliation, delegation success, and budget economics.

## H. Confidence and Unknowns

Observed:
- Delegate router mount gap
- Missing routing_decisions table in active DB
- Missing task_outcomes attribution columns in active DB
- Sparse runtime economics signals

Unknowns:
- Whether deployment profile intentionally excludes delegate surface today
- Whether some clients omit token metadata by design or due to incomplete integrations

## Evidence Snapshot

Runtime diagnostic command:
- c:/Users/kas41/.virtualenvs/The_Veil-qEYNbl89/Scripts/python.exe scripts/diagnose_gen_observability.py

Key outputs:
- routing_decisions: None
- task_outcomes: 1
- delegation_log: 0
- budget_states: 1
- cost_accuracy: None

Schema gaps reported:
- routing_decisions missing (full table absent)
- task_outcomes missing active_llm, prompt_intent, prompt_scope, suggested_llm
- cost_accuracy missing table columns

---
This report is paired with structured artifacts in this folder:
- inventory.yaml
- scorecards.yaml
- gap-register.yaml
- recommendation-register.yaml
