---
name: env-var-override-for-test-path-assumptions
type: pattern
confidence: 0.90
source_learnings: [2026-05-21-env-var-override-for-test-path-assumptions]
description: Learning: Add env-var override when test files hardcode relative path chains
tags: []
---

# Learning: Add env-var override when test files hardcode relative path chains

## What We Learned

When a pytest (or similar) test resolves a sibling project via a chain of `.parent.parent...`, add an env-var override (`FOO_DIR_OVERRIDE`) and a layout comment explaining the chain. The pattern:

```python
# Layout: <dir1>/ → <dir2>/ → ... → <target>/
# Override with FOO_DIR_OVERRIDE env var if layout changes.
TARGET_DIR = (
    Path(os.environ["FOO_DIR_OVERRIDE"])
    if "FOO_DIR_OVERRIDE" in os.environ
    else Path(__file__).parent.parent... / "target"
)
```

The `"KEY" in os.environ` guard before `os.environ["KEY"]` prevents KeyError. The comment documents the assumption at the point of use.

## Why It Matters

Silent path assumption breaks are hard to debug. A reader seeing `Path(__file__).parent.parent.parent.parent` has no idea what directory layout is assumed. The comment + override makes the assumption explicit and survivable when the plugin is relocated.

## Source

hook-audit epic fixture-guard-mcp-layout-2026-05-21, task-2 (test_mcp_node_smoke.py). Generalises to any test file resolving external project directories via relative chain.
