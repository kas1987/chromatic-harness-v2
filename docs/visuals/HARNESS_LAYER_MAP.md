# Harness Layer Map

This diagram shows the full visual operating stack.

```mermaid
flowchart TD
    L0[Layer 0: Human Intent] --> L1[Layer 1: Project State]
    L1 --> L2[Layer 2: ChromaticTrees Governance]
    L2 --> L3[Layer 3: Playbooks]
    L3 --> L4[Layer 4: Agent Router]
    L4 --> L5[Layer 5: Confidence Gate]
    L5 --> L6[Layer 6: Agent Execution]
    L6 --> L7[Layer 7: Validation]
    L7 --> L8[Layer 8: Event Logs]
    L8 --> L9[Layer 9: Visual Surfaces]

    L9 --> M[Mermaid / GitHub Docs]
    L9 --> N[n8n Workflow View]
    L9 --> G[Grafana / Tempo / Prometheus / Loki]
    L9 --> LS[LangGraph / Agent Trace View]
```

## Interpretation

- `CHROMATIC_TREES.md` governs repo structure.
- Playbooks govern behavior.
- Router selects the agent or model.
- Confidence gate authorizes or blocks action.
- Execution produces events.
- Events feed visual surfaces.
