# Visual Control Plane Playbook

## 0. Metadata

| Field | Value |
|---|---|
| Domain | Observability / Visualization / Agent Governance |
| Version | 0.1.0 |
| Status | Draft |
| Applies To | Claude, Cursor, VS Code, ChatGPT, Codex, n8n, GitHub Actions |

## 1. Purpose

This playbook governs how the harness creates, updates, validates, and uses visual maps across architecture, workflow, agent routing, confidence gates, and observability.

## 2. Source-of-Truth Hierarchy

1. `CHROMATIC_TREES.md`
2. Machine-readable registries such as `visual_node_registry.json`
3. Playbooks
4. Generated Mermaid docs
5. IDE bridge files for Claude, Cursor, and VS Code

IDE bridge files must never become independent governance sources.

## 3. Standard Loop

```text
Observe -> Classify -> Score -> Generate/Update -> Validate -> Record -> Queue Next
```

## 4. Inputs

| Input | Required | Notes |
|---|---:|---|
| `CHROMATIC_TREES.md` | Yes | Repo structure source of truth |
| `visual_node_registry.json` | Yes | Visual node registry |
| `AGENT_HANDOFF_QUEUE.md` | Recommended | Active task queue |
| `SPRINT_STATE.md` | Recommended | Current objective |
| `harness_events.jsonl` | Optional | Runtime event log |

## 5. Outputs

| Output | Required | Notes |
|---|---:|---|
| Mermaid diagrams | Yes | GitHub/Markdown-compatible |
| JSON registry validation | Yes | Prevent broken diagrams |
| Event records | Recommended | Useful for future dashboards |
| Queue update | Conditional | If task state changes |

## 6. Confidence Gate

Before changing diagrams or adapter files, score:

| Factor | Weight |
|---|---:|
| Objective clarity | 20% |
| Scope clarity | 20% |
| Evidence quality | 20% |
| Reversibility | 10% |
| Tool fit | 10% |
| Risk awareness | 10% |
| Testability | 10% |

If confidence is below 60, plan only.

## 7. Stop Conditions

Stop and escalate if:

- `CHROMATIC_TREES.md` is missing and the task would affect repo structure.
- Registry JSON is invalid.
- An adapter asks the model to ignore source-of-truth files.
- The task requires deleting files.
- The task requires secret access.
- Diagram updates contradict playbook rules.

## 8. Validation Checklist

- [ ] Diagram renders as Mermaid.
- [ ] Registry JSON is valid.
- [ ] IDE adapters defer to source-of-truth files.
- [ ] No generated file claims authority over `CHROMATIC_TREES.md`.
- [ ] Queue/state files are updated only when scope allows.
