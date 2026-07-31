# Domain docs

How engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, if it exists.
- **`CONTEXT-MAP.md`** at the repo root, if it exists — points at one `CONTEXT.md` per context.
- **`docs/adr/`** — architectural decision records.
- **`00_SOURCE_OF_TRUTH/`** — canonical execution flow, canon registry, and authority declarations.
- **`docs/governance/`** — policies that govern agent behavior and git autonomy.

If any file doesn't exist, proceed silently. The `mattpocock-domain-modeling` skill creates them lazily when terms or decisions actually get resolved.

## File structure

This is treated as a **single-context repo** with rich subsystem documentation.

```
/
├── AGENTS.md          ← canonical agent instructions
├── CONTEXT.md         ← domain model/glossary (created lazily)
├── 00_SOURCE_OF_TRUTH/
│   ├── HARNESS_EXECUTION_FLOW.md
│   └── canon_registry.yaml
├── docs/
│   ├── adr/           ← architectural decisions
│   ├── governance/    ← policies (git, context, CRG)
│   ├── beads/         ← beads workflow docs
│   └── agents/        ← this directory
└── .agents/
    ├── skills/        ← skill mirror
    └── handoffs/      ← session handoffs
```

## Use the glossary's vocabulary

When output names a domain concept (issue title, refactor proposal, hypothesis, test name), use the term as defined in `00_SOURCE_OF_TRUTH/canon_registry.yaml` or `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept isn't in the glossary yet, reconsider whether you're inventing language the project doesn't use, or note the gap for `mattpocock-domain-modeling`.

## Flag canon conflicts

If your output contradicts an existing ADR or canon entry, surface it explicitly rather than silently overriding:

> _Contradicts `00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md` line X — but worth reopening because…_
