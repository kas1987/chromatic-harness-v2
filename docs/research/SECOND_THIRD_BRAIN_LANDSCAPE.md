# Second Brain / Third Brain / Agent Memory Landscape

## Executive Summary

This document catalogs the emerging ecosystem of **persistent memory systems** for AI agents — from personal knowledge bases ("second brain") to multi-agent shared memory ("third brain"). These systems are the foundational layer that turns stateless AI agents into stateful, learning, coordinated systems.

---

## Tier 1: Multi-Agent Shared Memory ("Third Brain")

| Repo | Stars | Language | Key Idea | Why It Matters |
|---|---|---|---|---|
| **[pkyanam/brainbase](https://github.com/pkyanam/brainbase)** | 7 | TypeScript | Knowledge graph API for AI agents; Postgres + pgvector + Neo4j; MCP server with 23 tools | **The reference architecture** for company-wide agent memory. Polyglot storage, nightly "dream cycle" for auto-maintenance, graph intelligence |
| **[ldclabs/anda-brain](https://github.com/ldclabs/anda-brain)** | 59 | Rust | Bio-inspired graph memory with sleep-based consolidation; KIP + AndaDB | **Cognitive science grounded.** Handles contradiction detection, temporal relationships, memory evolution. Neural-symbolic AI approach |
| **[Haustorium12/memory-v3](https://github.com/Haustorium12/memory-v3)** | 2 | Python | 4-layer MAGMA graph (semantic/temporal/causal/entity), 3-stage retrieval, ACT-R + surprise scoring, constitutional governance | **Most sophisticated retrieval.** 24 MCP tools, full local-first (Ollama embeddings), Zettelkasten self-linking |
| **[beckfexx/BrainDB](https://github.com/beckfexx/BrainDB)** | 4 | TypeScript | Local-first AI memory + multi-agent orchestrator; 110 REST endpoints, 51 MCP tools, SQLite + FTS5 | **Best API surface.** Full contradiction detection, multi-agent heartbeats/claims, nightly self-learning pipeline |
| **[0xyaya/brain](https://github.com/0xyaya/brain)** | 0 | JavaScript | Graph-native memory; push JSON experiences, recall with hybrid semantic+graph search | **Zero-infrastructure.** Single graph file, works with any agent, edge-weight decay model |
| **[Chachamaru127/harness-mem](https://github.com/Chachamaru127/harness-mem)** | 26 | TypeScript | Local SQLite memory per project; Claude Code + Codex continuity runtime | **Best for coding agents.** 5ms cold start, private-tag stripping, project isolation, dual-agent coordination |
| **[yantrikos/brain](https://github.com/yantrikos/brain)** | 3 | Python | Persistent cognitive memory plugin; hybrid search (semantic + graph + temporal + keyword), personality traits, bond evolution | **Relationship-aware.** Tracks user-agent bond state, mood, intent. SQLite-only, <60ms latency |

### Architecture Patterns Observed

```
Third Brain Stack (consensus from repos above):
┌─────────────────────────────────────────────┐
│  MCP / REST API layer (agent interface)     │
├─────────────────────────────────────────────┤
│  Retrieval pipeline: coarse → fine → organize│
│  (BM25 + vector + graph traversal + RRF)      │
├─────────────────────────────────────────────┤
│  Storage polyglot:                           │
│  • Postgres/pgvector (system of record)       │
│  • Neo4j / NetworkX (graph projection)        │
│  • SQLite + FTS5 (local-first)               │
├─────────────────────────────────────────────┤
│  Background consolidation ("dream cycle")   │
│  • Extract links & entities                  │
│  • Detect contradictions                     │
│  • Auto-link orphans via similarity          │
│  • Temporal decay & surprise scoring         │
└─────────────────────────────────────────────┘
```

---

## Tier 2: Personal Knowledge Base ("Second Brain")

| Repo | Stars | Language | Key Idea | Best For |
|---|---|---|---|---|
| **[huytieu/COG-second-brain](https://github.com/huytieu/COG-second-brain)** | 494 | Shell | Self-evolving second brain; 17 AI skills, 6 worker agents, Obsidian + Git | **Team intelligence.** Daily briefs, meeting transcripts, team-brief with GitHub/Linear/Slack sync |
| **[NicholasSpisak/second-brain](https://github.com/NicholasSpisak/second-brain)** | 358 | Shell | LLM-maintained personal wiki; raw/ → wiki/ pipeline, Obsidian graph view | **Research ingestion.** Academic papers, articles → structured wiki with cross-references |
| **[polleoai/athena](https://github.com/polleoai/athena)** | 0 | TypeScript | Obsidian plugin; 3-layer architecture (raw/wiki/schema), Gryphon chat, kb CLI | **Obsidian-native.** URL/paper ingestion, bidirectional cross-references, soft-delete rollback |
| **[jessepinkman9900/claude-second-brain](https://github.com/jessepinkman9900/claude-second-brain)** | 39 | JavaScript | Karpathy LLM-Wiki pattern; Claude + qmd + Obsidian + GitHub | **Quick start.** One `npx claude-second-brain` scaffolds everything |
| **[Mathews-Tom/VaultMind](https://github.com/Mathews-Tom/VaultMind)** | 6 | Python | Hybrid search (vector + BM25), knowledge graph, Telegram bot, MCP integration | **Mobile capture.** Telegram bot for photo/audio capture, Zettelkasten maturation, belief evolution tracking |
| **[markfive-proto/obsidian-brain-vault](https://github.com/markfive-proto/obsidian-brain-vault)** | 3 | TypeScript | Community Karpathy wiki; CLI (`obs`) + MCP + Claude Code skills | **Unix philosophy.** Pipeable, scriptable, cron-able. `obs kb ingest` + `/clip` slash command |
| **[iurykrieger/claude-bedrock](https://github.com/iurykrieger/claude-bedrock)** | 51 | HTML/TS | Claude Code plugin; 7 entity types (actors/people/teams/topics/discussions/projects/fleeting), Zettelkasten | **Entity-centric.** Business rules as typed entities, bidirectional wikilinks, external source ingestion |
| **[aiplay/oh-my-brain](https://github.com/aiplay/oh-my-brain)** | 1 | TypeScript | Obsidian vault template; multi-agent orchestration hub, folder coloring, external repo mounting | **Multi-repo coordination.** Mount any local repo as vault subdirectory, symlink CLAUDE.md |

---

## Tier 3: Agent Harness / Memory Layer

| Repo | Stars | Language | Key Idea | Best For |
|---|---|---|---|---|
| **[giulio-leone/harness-os](https://github.com/giulio-leone/harness-os)** | 4 | TypeScript | "OS for autonomous AI agents"; SQLite canonical store, leases, task lifecycle, mem0 memory | **Task orchestration.** Zod plan contracts, session contracts, skill-policy registry, deterministic evidence gates |
| **[smc2315/harness-memory](https://github.com/smc2315/harness-memory)** | 2 | TypeScript | Project memory for coding harnesses; 4-layer activation engine (baseline/startup/scoped/diversity) | **Token-efficient memory.** 73% fewer tokens than CLAUDE.md via selective injection, human review gate |
| **[GregStarling/memory-layer](https://github.com/GregStarling/memory-layer)** | 0 | TypeScript | Cognitive memory architecture; turn → compaction → working → knowledge → context assembly | **Context assembly.** Token-budgeted context window, trust scoring, contradiction detection, multi-tenant scoping |
| **[Alenryuichi/openmemory-plus](https://github.com/Alenryuichi/openmemory-plus)** | 18 | TypeScript | xMemory 4-layer (L0 message → L1 episode → L2 semantic → L3 theme); multi-IDE support | **IDE-agnostic memory.** Unified layer for Gemini, Augment, Claude, Cursor — one memory everywhere |
| **[tbhrc/agentic-harness](https://github.com/tbhrc/agentic-harness)** | 0 | Python | Portable `.agent/` folder; memory + skills + protocols; plugs into Claude/Cursor/Windsurf/OpenCode | **Project portability.** `.agent/memory/memos/` append-only JSONL, autonomous semantic promotion |
| **[wearethecompute/openfused](https://github.com/wearethecompute/openfused)** | 3 | Rust | Encrypted, signed, peer-to-peer file protocol for agent context; age + Ed25519 | **Decentralized agent mesh.** Multi-agent workspaces, encrypted DMs, no vendor lock-in |

---

## Recommendations for Chromatic Harness v2

### Immediate Integration Targets

1. **Brainbase** (API-first) — Wire as a governed sidecar for company-wide knowledge graph. MCP-compatible, 23 tools, graph intelligence.

2. **harness-mem** (Local-first) — Use per-project for Claude Code + Codex continuity. 5ms cold start, zero cloud.

3. **memory-v3** (Research-grade) — Study the 4-layer MAGMA architecture and 3-stage retrieval pipeline for our router's context assembly layer.

### Architecture Gaps to Fill

| Gap | Current State | Target (from landscape) |
|---|---|---|
| Contradiction detection | None | BrainDB / anda-brain |
| Graph-native memory | None | Brainbase / memory-v3 |
| Nightly consolidation | None | Brainbase "dream cycle" |
| Multi-agent coordination | None | OpenFused / BrainDB |
| Token-budgeted context | Router logs only | memory-layer / harness-memory |
| Surprise scoring | None | memory-v3 Titans-inspired |
| Temporal decay | None | anda-brain / second-brain |

### Implementation Priority

```text
P1: Local SQLite memory store (harness-mem pattern) — per-project, zero cloud
P2: Graph projection layer (brainbase pattern) — Neo4j or NetworkX for relationships
P3: MCP server surface (brainbase pattern) — expose memory as tools to any agent
P4: Nightly consolidation daemon (anda-brain pattern) — background graph maintenance
P5: Cross-agent sync (OpenFused pattern) — encrypted peer-to-peer context sharing
```

---

## 2025-2026 Trending Projects (From Community)

Projects actively discussed on Reddit, Hacker News, and Discord in 2025-2026.

| Repo | Stars | Language | Key Idea | Why It Matters |
|---|---|---|---|---|
| **[tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman)** | 29k | Rust/TS | Personal AI with local Memory Tree + Obsidian-style vault | **Highest star count.** Local-first, self-hosted. Memory Tree = temporal knowledge graph with decay. OpenHuman adapter already integrated into Chromatic Router |
| **[Mark393295827/third-brain-v5-skills](https://github.com/Mark393295827/third-brain-v5-skills)** | ~100 | Markdown | Skills framework for Codex CLI, Claude Code, Gemini CLI, Cursor, Windsurf | **Multi-IDE third brain.** Daily review automation, agent team orchestration, persistent interlinked knowledge wiki. MIT licensed |
| **[Per0x1de-1337/MemoryOS](https://github.com/Per0x1de-1337/MemoryOS)** | New | Python | Temporal knowledge graph + hybrid vector retrieval + Ebbinghaus decay | **Sub-100ms retrieval.** Open-source Python memory layer. Automatic memory consolidation, cross-session continuity |
| **A-MEM** (HN "Show HN") | ~50 | Python | Zettelkasten-inspired for Claude Code; ChromaDB, self-evolving untyped graph | **Self-evolving memory.** Time-aware breadth/depth-first recall. No schema — graph grows organically from agent interactions |

### Community Sentiment (Reddit / HN / Discord)

- **OpenHuman**: Praised for being "actually local" (not cloud-washed). Criticized for Rust build complexity. Memory Tree feature is the #1 reason people try it.
- **Third Brain V5**: The "skills" pattern (markdown files + YAML frontmatter that agents read as instructions) is becoming a de-facto standard across Codex CLI and Claude Code communities.
- **MemoryOS**: HN commenters skeptical of "Ebbinghaus" marketing but impressed by sub-100ms retrieval benchmark. Temporal knowledge graphs are seen as the next evolution over simple vector DBs.
- **A-MEM**: Loved by Claude Code users for being "zero-config" — just install and it starts building a graph from your chat history. Criticized for ChromaDB dependency (heavy, sometimes flaky).

---

## Key Insight

> **The value of an agent memory system is directly proportional to how automatically it is used.**
> — Brainbase (inspired by YC Company Brain RFS)

Passive memory (RAG over documents) is a search engine.
Active memory (auto-extraction, contradiction detection, nightly consolidation) is a second brain.
Shared memory (multi-agent graph, coordination protocols) is a third brain.

Chromatic Harness v2 should evolve from **passive** (logs & JSONL) → **active** (auto-extracted learnings, scope violation detection) → **shared** (inter-agent knowledge graph, governed OpenHuman bridge).
