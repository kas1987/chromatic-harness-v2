# Chromatic Vector Architecture & Semantic Memory Strategy

**Bead:** mc-vei8i (CC #38)  
**Status:** Design v1.0  
**Date:** 2026-06-19

---

## Overview

The Chromatic Vector Architecture defines how semantic memory is stored, retrieved, and used across the harness. The goal is to give agents persistent, searchable context about past decisions, patterns, and project state — without requiring full transcript replay.

---

## Principles

1. **Local-first.** Vectors are stored on disk, not in a cloud vector DB. No egress cost, no auth complexity.
2. **Append-only writes.** Embeddings are never modified after creation. Corrections append new entries with a `supersedes` field.
3. **Lazy indexing.** Embeddings are generated at write time, not read time. Retrieval is fast; ingestion pays the embedding cost once.
4. **Tiered retrieval.** Fast exact-match (keyword) first, then semantic search for fuzzy recall. Avoids embedding lookup for simple queries.

---

## Memory Tiers

### Tier 1: Session Memory (ephemeral)

- Scope: current Claude Code session
- Storage: in-context (no disk write)
- Retrieval: implicit (already in window)
- TTL: session end

### Tier 2: Project Memory (persistent, structured)

- Scope: `~/.claude/projects/<project>/memory/`
- Storage: markdown files with YAML frontmatter
- Retrieval: `MEMORY.md` index → Read tool
- TTL: manual (user manages)
- Examples: user preferences, project state, feedback patterns

### Tier 3: bd Knowledge Base (persistent, searchable)

- Scope: `~/.beads` Dolt database
- Storage: `bd remember "<insight>"` writes to `knowledge` table
- Retrieval: `bd recall "<query>"` (keyword search)
- TTL: permanent (Dolt history)

### Tier 4: Semantic Index (persistent, vector-based)

- Scope: `.agents/semantic/`
- Storage: JSON lines with embedding vectors + source metadata
- Retrieval: cosine similarity search over embedding vectors
- TTL: permanent (append-only)
- **Status: Planned (not yet implemented)**

---

## Semantic Index Format

Each entry in `.agents/semantic/index.jsonl`:

```json
{
  "id": "sem-001",
  "created_at": "2026-06-19T14:00:00Z",
  "source": "bd:mc-rxu05",
  "text": "Agent control loop design: queue protocol uses claim gates to prevent concurrent execution of the same task.",
  "tags": ["architecture", "agent", "queue"],
  "embedding": [0.123, -0.456, ...],
  "model": "text-embedding-3-small",
  "supersedes": null
}
```

### Embedding Model Selection

| Use Case | Model | Dimensions | Cost |
|----------|-------|------------|------|
| Default (all harness content) | `text-embedding-3-small` | 1536 | $0.02/1M tokens |
| High-precision (governance docs) | `text-embedding-3-large` | 3072 | $0.13/1M tokens |
| Offline / no API | local ONNX model | 384 | free |

Default: `text-embedding-3-small`. Override via `CHROMATIC_EMBED_MODEL` env var.

---

## Retrieval Strategy

### Step 1: Exact match (keyword)

```python
results = [e for e in index if any(tag in e["tags"] for tag in query_tags)]
```

If ≥3 results: return top 5 by recency. Skip semantic search.

### Step 2: Semantic search (cosine similarity)

```python
q_vec = embed(query_text)
scored = [(cosine(q_vec, e["embedding"]), e) for e in index]
scored.sort(reverse=True)
return [e for _, e in scored[:5]]
```

Threshold: only return results with cosine similarity > 0.75.

### Step 3: Synthesis

Top results from either step are injected into the agent prompt as:

```
## Relevant Context (from semantic memory)
1. [2026-06-19] Agent control loop: claim gates prevent concurrent task execution.
2. [2026-06-18] pytest TIME_WAIT fix: use module-scoped fixtures to avoid port rebind on Windows.
```

---

## Write Paths

### Manual write (bd remember)

```bash
bd remember "module-scoped pytest fixtures avoid TIME_WAIT on Windows port rebind"
```

bd CLI writes to Dolt knowledge table. Background job queues embedding generation.

### Automatic write (retro indexing)

After `/post-mortem`, learnings from `docs/retros/` are batch-indexed:

```bash
python scripts/index_retro.py docs/retros/2026-06-19-*.md
```

### Hook-triggered write (preflight events)

`cross-repo-preflight.sh` writes structured events to `.agents/events/preflight-events.jsonl`. A nightly cron indexes these into the semantic store.

---

## Query Interface

Agents query semantic memory via:

```python
from harness.semantic import recall

results = recall("pytest Windows port binding", top_k=5, threshold=0.75)
for r in results:
    print(r["text"], r["created_at"])
```

This is the planned interface. Implementation in `.agents/semantic/` is Phase 2.

---

## Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| P1 | Tiers 1–3 (session, project memory, bd knowledge) | Done |
| P2 | Tier 4 local semantic index (JSONL + cosine) | Planned |
| P3 | Embedding generation pipeline (index_retro.py, nightly cron) | Planned |
| P4 | Semantic query interface in harness agents | Planned |
| P5 | Cross-repo federation of semantic indexes | Future |

---

## Related

- `HARNESS_KERNEL.md` — memory compression in Nano/Lite tiers
- `CHROMATIC_DICTIONARY.md` — term definitions (embedding, semantic index)
- `docs/retros/` — source material for Tier 4 indexing
- `~/.claude/projects/.../memory/` — Tier 2 project memory
