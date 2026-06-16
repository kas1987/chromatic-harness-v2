# Decision: Canonical Autonomy Scale = L0–L5

**Date:** 2026-06-16
**Status:** DECIDED — unblocks Phase 3 (mode switcher)
**Scope:** `01_PROTOCOLS/CMP/mission_packet.schema.json`, the Command Prompt System modes, the console.

---

## Decision

The canonical autonomy scale is **`L0`–`L5`** (string, `L`-prefixed), exactly as
already implemented in `01_PROTOCOLS/CMP/mission_packet.schema.json`:

```json
"autonomy_level": {"type": "string", "enum": ["L0", "L1", "L2", "L3", "L4", "L5"]}
```

No code change is required to adopt this — it is the de-facto standard already in
the schema and runtime.

## Why (evidence)

- `mission_packet.schema.json` enumerates `L0`–`L5` (6 levels, string).
- Autonomy levels are referenced ~**64×** in `02_RUNTIME`, ~**52×** in `tests/`,
  ~**36×** in `05_FRONTEND_CONSOLE/src`. Changing the scale would cascade across
  150+ sites including the test suite for no functional benefit.
- A direct grep of `CHROMATIC_TREES.md` finds **no concrete competing
  `C1–C4 / L0–L4` autonomy enum**. The earlier integration blueprint's
  "L0–L5 vs C1–C4/L0–L4 mismatch" conflated two *different axes*:
  - **L-levels (`L0`–`L5`)** = **autonomy** (how much the agent may do unattended).
  - **C-levels (`C1`–`C4`)**, where referenced, = **confidence tiers** — a separate
    axis, not an alternative autonomy scale.
  There is therefore nothing to "reconcile" in code; this is a documentation
  clarification, not a refactor.

## Phase-3 mode bands bind to L0–L5

The Command Prompt System modes (per the PDRs) map directly onto this scale:

| Mode | Default autonomy band |
|------|-----------------------|
| Operator | `L3`–`L4` |
| Auditor | `L0`–`L2` |
| Designer | `L1`–`L3` |

The mode switcher (Phase 3) uses these bands as **advisory defaults only** — they
never override a CMP gate verdict (see `docs/design/PHASE3_MODE_NO_OVERRIDE_TEST.md`).

## Known debt (separate, low-priority follow-up — NOT part of this decision)

The frontend types autonomy as **numeric** (`api.ts`: `autonomy_level?: 0|1|2|3|4|5`,
`AgentProfile.current_level: 0|1|2|3|4|5`) while the backend schema is **string**
(`"L0".."L5"`). This is an API-boundary representation mismatch the console currently
bridges. Reconciling it (pick one representation end-to-end) is a separate, scoped
change touching `api.ts` types + ~36 frontend sites; it is **not** required to
unblock Phase 3 and is deferred.
