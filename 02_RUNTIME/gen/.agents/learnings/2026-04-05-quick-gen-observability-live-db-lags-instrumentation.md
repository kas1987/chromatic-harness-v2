---
type: learning
source: retro-quick
date: 2026-04-05
---

# Learning: Gen Observability Live DB Lags Instrumentation

**Category**: architecture
**Confidence**: medium

## What We Learned

The Gen observability code and docs are ahead of the live `gen.db` state. Until `routing_decisions` exists and `task_outcomes` is migrated to include `prompt_intent`, `prompt_scope`, `active_llm`, and `suggested_llm`, provider, tool-frequency, token, and cost analytics will look mostly empty even when the hook pipeline is active.

## Source

Quick capture via `/retro --quick`