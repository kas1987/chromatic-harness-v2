# Pre-Nodal Bond Inference System — Design Spec

**Date:** 2026-04-29  
**Status:** Approved for spec pass  
**Epic:** Graph Knowledge Platform Restructure (`D:/.04_Prism/docs/ways-of-work/plan/graph-knowledge-platform-restructure/epic.md`)  
**Shadow R&D:** Tensor decomposition upgrade path archived at `C:/Users/kas41/.agents/shadow-lab/2026-04-29-tensor-bond-discovery.md`

---

## One-Line Summary

> Canonical graph stores what was observed. Shadow graph stores what is believed. Audit graph stores why the system believed it and what later happened.

---

## Problem

The GraphRAG substrate (graphify → Neo4j projection) only captures explicitly extracted relationships. Large classes of structurally real bonds are invisible to it: files that co-evolve without explicit imports, concepts that cluster semantically without formal links, communities that share risk via hub nodes but have no direct edge. These latent bonds degrade retrieval recall and leave multi-hop reasoning blind to the graph's actual topology.

The solution is not to guess — it is to accumulate evidence, assign confidence, and let the shadow graph earn retrieval weight over time while keeping the canonical graph clean.

---

## Architecture: Three Permanent Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1 — Canonical Graph (explicit, auditable)             │
│   :Node ──[:RELATES]──> :Node                     │
│   Source: extraction (graphify, import scan, manual)        │
│   Mutated by: extraction events only                        │
│   Trust: high — provenance-backed, contract-validated       │
└─────────────────────────────────────────────────────────────┘
          ↕ traversal sees both layers
┌─────────────────────────────────────────────────────────────┐
│ Layer 2 — Shadow Graph (inferred, probabilistic)            │
│   :Node ──[:PREDICTED_BOND]──> :Node              │
│   Source: multi-signal Bayesian accumulator                 │
│   Mutated by: signal events only, never by threshold alone  │
│   Trust: confidence score 0.0–1.0, decays w/o reinforcement │
└─────────────────────────────────────────────────────────────┘
          ↕ all events logged to
┌─────────────────────────────────────────────────────────────┐
│ Layer 3 — Audit Trail (immutable event log)                 │
│   :DERIVED_FROM_SIGNAL, :CONFIRMED_BY, :INVALIDATED_BY      │
│   Source: system events                                     │
│   Mutated by: append-only, never modified                   │
│   Trust: append-only record of all layer 1 and 2 mutations  │
└─────────────────────────────────────────────────────────────┘
```

**Invariant:** No probabilistic edge may mutate the canonical graph without an explicit confirmation event. Confidence rising above a threshold triggers *operational workflow*, not *ontology mutation*.

---

## Neo4j Edge Model

### `:RELATES` — Canonical observed relationship

```cypher
(a:Node)-[:RELATES {
  relation_type:   string,    // 'depends_on' | 'contains' | 'calls' | 'exports' | ...
  provenance:      string,    // 'graphify_extract' | 'import_scan' | 'manual'
  source_ref:      string,    // file path, git sha, or doc location
  confidence:      float,     // extraction confidence (1.0 for explicit imports)
  extracted_by:    string,    // tool version (e.g. 'graphify-v2.1')
  confirmed_at:    datetime
}]->(b:Node)
```

### `:PREDICTED_BOND` — Shadow inferred relationship

```cypher
(a:Node)-[:PREDICTED_BOND {
  confidence:          float,     // current Bayesian posterior [0.0–1.0]
  signals:             string[],  // signal families that contributed (see below)
  independent_count:   int,       // count of distinct signal families (not observations)
  created_at:          datetime,  // immutable — never changes
  last_reinforced_at:  datetime,  // updated on each signal event
  retrieval_state:     string,    // 'active' | 'excluded' | 'pending_review'
  excluded_after:      datetime,  // null when active
  decay_reason:        string,    // null when active; 'no_reinforcement' | 'low_confidence'
  model_version:       string     // 'shadow-bond-v1'
}]->(b:Node)
```

**Identity rule:** `created_at` is immutable. `retrieval_state` is mutable. These are separate properties because edge identity and retrieval eligibility are different things.

### `:DERIVED_FROM_SIGNAL` — Audit: which signals built a predicted bond

```cypher
(bond:PREDICTED_BOND)-[:DERIVED_FROM_SIGNAL {
  signal_family:  string,    // one of the 5 canonical families (see below)
  observed_at:    datetime,
  strength:       float,     // per-observation signal strength [0.0–1.0]
  source:         string,    // what triggered this observation
  delta_confidence: float    // how much this observation moved the posterior
}]->(signal:SignalEvent)
```

### `:CONFIRMED_BY` — Audit: what confirmed or contradicted a bond

```cypher
(bond:PREDICTED_BOND)-[:CONFIRMED_BY {
  event_type:         string,   // see confirmation event types below
  confirmed_at:       datetime,
  confirming_entity:  string,   // tool name, user id, or query id
  mints_relates:      boolean   // whether this event type is allowed to create :RELATES
}]->(event:ConfirmationEvent)
```

### `:INVALIDATED_BY` — Audit: what killed a bond

```cypher
(bond:PREDICTED_BOND)-[:INVALIDATED_BY {
  reason:              string,
  invalidated_at:      datetime,
  invalidating_entity: string
}]->(event:InvalidationEvent)
```

### Event Node Schemas

These nodes anchor the audit trail. All three are append-only — never updated after creation.

**`:SignalEvent`** — one node per signal observation:
```cypher
(:SignalEvent {
  event_id:       string,    // uuid
  signal_family:  string,    // one of the 5 canonical family IDs
  strength:       float,     // per-observation strength [0.0–1.0]
  source:         string,    // what triggered this (e.g. 'graphify_run_2026-04-29', 'git_log_scan')
  observed_at:    datetime,
  delta_confidence: float    // how much this observation moved the posterior on its bond
})
```

**`:ConfirmationEvent`** — one node per confirmation:
```cypher
(:ConfirmationEvent {
  event_id:          string,
  event_type:        string,    // 'extraction_confirmed' | 'human_confirmed' | 'runtime_observed' | 'query_validated'
  confirming_entity: string,    // tool name, user id, or query id
  confirmed_at:      datetime,
  mints_relates:     boolean,
  new_relates_id:    string     // id of the newly minted :RELATES edge if mints_relates=true, else null
})
```

**`:InvalidationEvent`** — one node per invalidation:
```cypher
(:InvalidationEvent {
  event_id:            string,
  reason:              string,    // 'contradicted_by_extraction' | 'human_rejected' | 'decay_no_reinforcement' | 'decay_low_confidence'
  invalidated_at:      datetime,
  invalidating_entity: string
})
```

---

## Signal Families (Formal Definition)

**Independence rule:** Two observations count as independent only if they come from different signal families. Ten co-change observations count as one independent signal, not ten.

| Family | ID | Description | Source |
|--------|-----|-------------|--------|
| Co-change history | `co_change` | Files/nodes that appear in the same git commits over time | Git log, blame analysis |
| Import/reference extraction | `import_ref` | Explicit import, require, or reference relationships | Graphify, AST parsing |
| Embedding similarity | `embedding_sim` | Semantic similarity of node labels and content | Vector embedding comparison |
| Query co-traversal | `query_traversal` | Nodes that appear together in successful PageRank retrieval paths | HippoRAG query logs |
| Community bridge centrality | `community_bridge` | Nodes that act as structural bridges between communities across multiple graph runs | Leiden community detection |

**Minimum for cross-community bond activation:** ≥2 independent signal families must confirm before the cross-community penalty lifts and the bond becomes fully retrieval-eligible.

---

## Bayesian Update Model

### Priors

| Condition | P(bond) prior |
|-----------|--------------|
| Same Leiden community | 0.70 |
| Adjacent communities (1-hop) | 0.30 |
| Cross-community (2+ hops) | 0.10 |
| Hub node neighbor (degree > 80th percentile at bond-creation time) | prior + 0.10 |

### Update Rule

For each signal observation, update the posterior using a likelihood ratio:

```
P(bond | signal) = P(signal | bond_exists) × P(bond) 
                   / P(signal)
```

Simplified per-family likelihood ratios (initial values, calibrated from data over time):

| Signal family | L(signal | bond exists) | L(signal | no bond) |
|---------------|------------------------|----------------------|
| `co_change` | 0.85 | 0.15 |
| `import_ref` | 0.95 | 0.05 |
| `embedding_sim` | 0.70 | 0.40 |
| `query_traversal` | 0.75 | 0.30 |
| `community_bridge` | 0.80 | 0.25 |

**These ratios are initial estimates. The calibration loop (which predictions became real vs. which died) is what tunes them over time.**

---

## Traversal Weights

HippoRAG PageRank sees both layers. Edge weights:

| Edge type | Base weight | Modifier |
|-----------|-------------|----------|
| `:RELATES` | 1.0 | none |
| `:PREDICTED_BOND` (same community) | `confidence × 1.0` | none |
| `:PREDICTED_BOND` (cross-community, 1 signal) | `confidence × 0.5` | penalty until ≥2 signals |
| `:PREDICTED_BOND` (cross-community, ≥2 signals) | `confidence × 0.8` | penalty lifted |
| `:PREDICTED_BOND` (hub-sponsored) | `confidence × 1.2` | bonus for structural stability |
| Excluded bond (`retrieval_state = 'excluded'`) | 0 | not traversed |

---

## Decay and Exclusion

Predicted bonds degrade when not reinforced. This is intentional — the shadow graph should reflect current belief, not historical speculation.

| Trigger | Action |
|---------|--------|
| No reinforcement in 30 days | `retrieval_state → 'excluded'`, `decay_reason → 'no_reinforcement'` |
| `confidence < 0.3` | `retrieval_state → 'excluded'`, `decay_reason → 'low_confidence'` |
| Invalidation event | `retrieval_state → 'excluded'`, `decay_reason → from invalidation event` |

**Deletion policy:** Bonds are never deleted. `retrieval_state = 'excluded'` removes them from active traversal but preserves them in the audit record. The prediction history matters for calibration.

---

## Confirmation Event Types and Trust Policy

Not all confirmations are equal. Only some may mint a new `:RELATES` edge.

| Event type | Description | Can mint `:RELATES` |
|------------|-------------|---------------------|
| `extraction_confirmed` | Graphify or import scanner finds an explicit relationship | ✅ Yes |
| `human_confirmed` | A maintainer reviews and explicitly confirms the bond | ✅ Yes |
| `runtime_observed` | System observes the relationship used at runtime (e.g., function call trace) | ❌ No — raises confidence + triggers review queue |
| `query_validated` | HippoRAG retrieval traversal of this bond produced a high-relevance result | ❌ No — raises confidence only |

**Minting rule:** When a `mints_relates = true` confirmation occurs, a new `:RELATES` edge is created with its own provenance. The `:PREDICTED_BOND` is **not modified or deleted** — the prediction history remains alongside the confirmation. The `:CONFIRMED_BY` audit edge links them.

---

## Operational Actions Triggered by Confidence Thresholds

Confidence thresholds control *workflow*, not *ontology*.

| Threshold | Action |
|-----------|--------|
| `confidence ≥ 0.85` + `independent_count ≥ 2` | Add to review queue as extraction candidate |
| `confidence ≥ 0.70` + cross-community | Schedule targeted validation job |
| `confidence ≥ 0.60` | Raise bond visibility in retrieval (bond_type_factor boost) |
| `confidence < 0.30` | Exclude from active retrieval |
| `confidence < 0.10` | Flag for potential invalidation review |

---

## Components

### 1. Signal Collector (`apps/shadow/signal_collector.py`)
Listens for signal events from five families. Each observation is logged as a `SignalEvent` node and triggers a Bayesian update. Stateless — events are the source of truth.

### 2. Bayesian Updater (`apps/shadow/bayesian_updater.py`)
Reads current `:PREDICTED_BOND` confidence, applies the likelihood ratio update, writes back updated confidence and signal fields. Also evaluates `retrieval_state` transitions (active → pending_review → excluded).

### 3. Shadow Graph Writer (`apps/shadow/shadow_writer.py`)
Creates new `:PREDICTED_BOND` edges when a signal fires for a node pair with no existing prediction. Sets priors based on community membership. Idempotent — safe to re-run.

### 4. Confirmation Handler (`apps/shadow/confirmation_handler.py`)
Processes confirmation events. For `mints_relates = true` events: creates a new `:RELATES` edge with provenance, writes `:CONFIRMED_BY` audit edge to existing `:PREDICTED_BOND`.

### 5. Retrieval Adapter (`apps/retrieval/hipporag_retriever.py` — extend existing)
Extend the HippoRAG retriever to include `:PREDICTED_BOND` edges in the networkx graph, weighted per the traversal table above. Excluded bonds (`retrieval_state = 'excluded'`) are filtered before graph construction.

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Retrieval recall lift (shadow bonds vs. canonical only) | Measurable after 30 days of signal accumulation |
| Prediction accuracy (% of high-confidence bonds later confirmed) | Baseline in 6 months |
| Signal family calibration | Likelihood ratios converge within 20% of initial estimates |
| False positive rate (high-confidence bonds that get invalidated) | < 15% of bonds above 0.85 |

---

## Out of Scope

- Tensor decomposition (parked in Shadow R&D Lab — activates when ≥6 months of signal data exists)
- UI for reviewing the shadow graph (operational queue via API only for now)
- Quantum or quantum-inspired approaches
- Automatic migration of all existing graph data to this model in one pass

---

## Integration with GraphRAG Substrate Epic

This spec extends the GraphRAG substrate epic's projection layer. Insertion point:

- **After Wave 1** (graphify → Neo4j sync): Shadow graph writer can begin creating predicted bonds from the initial node set
- **After Wave 2** (community summaries): Community priors become accurate for the Bayesian updater
- **After Wave 3** (HippoRAG retriever): Retrieval adapter can be extended to include shadow bonds
- **Shadow components** ship as Wave 5 of the same epic or as a standalone follow-on epic

---

## Connection to Village-Cortex

The shadow graph is the "underground superhighway" — the latent connectivity layer that the village-cortex's capability registry and intent router will eventually traverse. When the cortex routes a request, it sees not just explicit tool dependencies but predicted bonds between tools that have been statistically observed to co-activate. The bonds that won't break are the ones sponsored by hub nodes (high-centrality tools that cover their neighbors' risk), exactly as described.
