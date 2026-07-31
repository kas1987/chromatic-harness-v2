# Chromatic Harness v2 — Domain Schema (GraphQL-style)

This is a conceptual schema, not a live endpoint. It describes the entities and relationships agents should understand when navigating the harness.

```graphql
type Repo {
  sourceOfTruth: [SourceLayer!]!
  runtimeState: [RuntimeLayer!]!
  agents: [Agent!]!
  skills: [Skill!]!
  beads: [Bead!]!
  missions: [Mission!]!
}

type SourceLayer {
  name: String!        # e.g., "scripts", "docs", "config", "skills"
  path: String!
  purpose: String!
  inGit: Boolean!      # true for canonical layers
}

type RuntimeLayer {
  name: String!        # e.g., "07_LOGS_AND_AUDIT", ".agents/handoffs"
  path: String!
  purpose: String!
  retention: String! # e.g., "session", "daily", "until regenerated"
}

type Agent {
  name: String!        # e.g., "codex", "claude", "pi"
  surface: ToolSurface!
  skills: [Skill!]!
}

type ToolSurface {
  name: String!        # "Cursor" | "VS Code" | "Codex CLI"
  nativeTools: [String!]!
  mcpServers: [String!]!
}

type Skill {
  name: String!
  namespace: String!   # "mattpocock-" or "agentops:" or "harness"
  trigger: String!
  tokenTier: String!   # xs | s | m | l | xl
}

type Bead {
  id: String!
  title: String!
  status: BeadStatus!
  priority: Int!
  parent: Bead
  children: [Bead!]
}

enum BeadStatus {
  open
  in_progress
  blocked
  closed
  deferred
}

type Mission {
  id: String!
  handoff: Handoff!
  beads: [Bead!]!
}

type Handoff {
  path: String!
  agent: String!
  lastCommit: String!
}
```
