# Claude Command: Audit Visual Control Plane

Audit the visual control plane using this checklist:

- Does `CHROMATIC_TREES.md` remain source of truth?
- Do Claude, Cursor, and VS Code adapters defer to source-of-truth docs?
- Does `visual_node_registry.json` validate?
- Do Mermaid files reflect current registry structure?
- Are confidence gates represented?
- Are observability events represented?
- Are n8n, Grafana, and agent-trace layers clearly separated?

Return findings as:

| Severity | Finding | Evidence | Fix |
|---|---|---|---|
