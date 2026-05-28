# OpenHuman Integration Boundary

## Phase 1: Sidecar Read-Only Context (Current)

Allowed:
- health check
- memory search / query
- non-destructive integration summaries
- read-only contextual handoff

Forbidden:
- sending emails
- modifying calendars
- mutating GitHub
- deleting files
- writing to Chromatic source-of-truth memory
- acting as primary orchestrator

## Phase 2: Governed Tool Execution (Future)

Requirements for every tool execution:
- task ID
- allowed tool list
- allowed account/integration list
- privacy class
- budget cap
- stop conditions
- full audit log

## Phase 3: Bidirectional Memory Bridge (Future)

Allowed bridge types:
- project summaries
- user-approved context capsules
- non-secret workflow state
- final decisions

Forbidden bridge types:
- API keys
- raw private inbox exports
- raw calendar dumps
- uncontrolled repo files
- sensitive personal records

## Configuration

See `config/routing/openhuman.yaml.example`.
