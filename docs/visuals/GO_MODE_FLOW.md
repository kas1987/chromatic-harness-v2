# GO-Mode Flow

```mermaid
flowchart TD
    A[User says GO] --> B[Read Project State]
    B --> C[Read Handoff Queue]
    C --> D[Read ChromaticTrees]
    D --> E[Classify Task]
    E --> F[Score Confidence]

    F -->|90-100| G[Autonomous Scoped Execute]
    F -->|75-89| H[Dispatch Scoped Agent]
    F -->|60-74| I[Reversible Low-Risk Action]
    F -->|40-59| J[Plan Only]
    F -->|0-39| K[Halt and Human Gate]

    G --> L[Validate]
    H --> L
    I --> L
    J --> M[Queue Planning Task]
    K --> N[Escalation Note]

    L --> O[Record Event]
    O --> P[Update Queue]
    P --> Q[Generate Visuals]
```

## Required GO-mode files

- `SPRINT_STATE.md`
- `AGENT_HANDOFF_QUEUE.md`
- `CHROMATIC_TREES.md`
- `DECISION_LOG.md`
- `RISK_REGISTER.md`
- `docs/playbooks/VISUAL_CONTROL_PLANE_PLAYBOOK.md`
