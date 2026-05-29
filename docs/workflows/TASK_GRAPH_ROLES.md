# Task Graph Roles (lite pipeline)

Standard four-step graph for bounded work (no swarm):

| Step | Role | Model | Purpose |
|------|------|-------|---------|
| 1 | `scout` | sonnet | Research / scope |
| 2 | `worker` | kimi | Implement |
| 3 | `verifier` | sonnet | Review gates |
| 4 | `scribe` | kimi | Handoff + logs |

## Generate graph

```bash
python scripts/workflow_go.py "GO DEEP"
# writes .agents/workflows/active-graph.json
```

Or programmatically:

```python
from workflows.roles import build_standard_pipeline, write_active_graph
write_active_graph(build_standard_pipeline("My objective", bead_id="chromatic-harness-v2-abc"))
```

## Schema

Roles must match [TASK_GRAPH_SCHEMA.json](TASK_GRAPH_SCHEMA.json) `role` enum.
