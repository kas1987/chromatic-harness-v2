# Routing & Governance Enforcement — Design

**Date:** 2026-04-30
**Owner:** kas41
**Status:** approved (brainstorm), pending plan

## Problem

Per-turn cost in the last 7 days doubled from a $0.05 baseline to $0.12.
The CCC log analyzer (`scripts/ccc_logs_analyze.py`) attributes the drift to
two leaks:

1. **Routing recommendations are advisory, not enforced.** The
   `governance-router.py` UserPromptSubmit hook writes a `[GOVERNANCE-ROUTING]`
   block to context with a recommended `(model, effort)`, floor, and ceiling.
   The Claude Code runtime does not consult this when picking the model.
   Sampled session `a65a5f29-050f-4dba-82bb-b2a8caed48e8` shows 261 turns
   running on Opus despite the router flagging every turn as
   `single_file_edit / sonnet_4_6/low` with a Sonnet ceiling. 145 routing-log
   entries with Sonnet ceilings exist; 7 of 24 sessions in the 7-day window
   ran Opus as primary.

2. **GOL harness is not in the call path.** `~/.harness/logs/turns.jsonl` last
   wrote at 2026-04-29; heartbeat is stale 24 h. The harness routes T1 lookup
   prompts dispatched explicitly through `harness <prompt>`, but Claude Code
   sessions go directly to the Anthropic API. Budget-mode and Featherless
   lanes configured in `routing-table.yaml` are unreachable for in-session
   work. The 24 sessions / $328 spend in the last 7 days have zero entries
   in the harness turns log.

## Goal

Enforce the routing table at the prompt boundary using a layered defense.
Use the harness binary as the single source of truth for routing decisions.
Provide a delegation lane so cheap-tier work can leave the Anthropic API
entirely when feasible. Surface non-blocking soft violations as aggregated
visibility, not per-event noise.

## Non-Goals

- **Mid-session model swap.** Claude Code hooks cannot change the runtime
  model for the current turn. The user must invoke `/model` themselves.
- **Auto-routing Sonnet-class work to Featherless.** That requires changing
  how Claude Code starts and how its responses stream back; out of scope.
- **Replacing the Anthropic API as the primary lane.** Anthropic remains the
  default; delegation is opt-in and narrow.

## Architecture

### Layer 1 — Canonical decision (harness-route)

A new UserPromptSubmit hook calls
`~/.harness/harness --route-only --json "<prompt>"` and writes the result to
`~/.claude/state/harness-route.json`. Runs *before* the existing
`governance-router.py`. The harness's classifier output (call_type, tier,
floor, ceiling, recommended model) becomes the canonical decision for all
downstream layers.

If the harness is unhealthy (heartbeat stale > 1 h, or process fails), the
hook falls back to writing a `degraded: true` flag in the state file. Layer 2
treats degraded state as soft-warn-only.

### Layer 2 — Ceiling enforcer

A new UserPromptSubmit hook reads the cached decision plus the current
session model from hook input. Computes:

- `actual_rank` = position of current model in `[ollama, haiku, sonnet, opus]`
- `ceiling_rank` = position of recommended ceiling

**Behavior:**

| Condition | Action |
|---|---|
| `actual_rank > ceiling_rank + 1` (2-tier breach) | **Hard block.** Hook exits 2 with a one-line message: "Opus on `<call_type>` (ceiling: Sonnet). `/model sonnet` and resubmit, or `/delegate` to dispatch via harness." Original prompt path is preserved (Claude Code retains the user's text). |
| `actual_rank == ceiling_rank + 1` (1-tier breach) | **Counter.** Increment `~/.claude/state/routing-violations-counter.jsonl` with `{ts, call_type, ceiling, actual}`. No block, no in-context message. |
| `actual_rank <= ceiling_rank` | **Compliant.** Counter increment for the compliance side. |

When harness is degraded (Layer 1 fallback), even 2-tier breaches downgrade
to soft-warn — never block based on a degraded classifier.

### Layer 3 — Pre-compute delegation (opt-in)

A new UserPromptSubmit hook gated by `HARNESS_PRECOMPUTE=true` env var.
Activates only when the cached harness decision has
`model_id == "ollama_resident"` AND `call_type in {lookup, documentation}`.

Behavior: dispatch the prompt through `harness "<prompt>" --json` (full run,
not route-only), capture the answer, inject it into context as
`additionalContext` with the marker `[OL-precomputed]`. Claude sees the
answer alongside the original prompt and is expected to either pass it
through or extend it without re-doing the work.

Failure mode: if the harness call exceeds 10 s or returns no usable output,
silently skip — do not inject anything. The user's prompt proceeds normally.
Off by default. The user enables it once they've validated harness output
quality on a sample workload.

### Layer 4 — Stop-time accounting

Three Stop hooks, building on the pieces shipped on 2026-04-30:

- `ccc-routing-violation.py` (existing): updated to read from
  `~/.claude/state/harness-route.json` instead of re-classifying.
- `ccc-session-footer.py` (existing): adds a `compliance_pct` field to its
  per-session JSONL record.
- `frequency-aggregator.py` (new): runs three modes —
  - **Daily**: triggered by Stop hook once per UTC day. Emits a one-line
    digest to a project log: "Last 24h: 3 hard blocks, 47 soft-1-tier
    breaches, ~$8 saved by L3." Disable with `touch ~/.claude/.ccc-daily-off`.
  - **Weekly**: on-demand or scheduled via the `/schedule` skill. Writes a
    Markdown summary to `~/.claude/state/ccc-weekly-digest.md`.
  - **Lazy on-click**: a `/ccc-digest` slash command that prints the
    current week-to-date digest immediately without waiting for the cron.

### Layer 5 — Slash commands

Two new skills under `~/.claude/skills/`:

- **`/delegate`** — `delegate <prompt>` or `delegate --tier=cloud <prompt>`.
  Dispatches via the harness, prints the result. Used as the relief valve
  when Layer 2 hard-blocks. Supports `--strict-budget` to force budget-mode
  routing.
- **`/model-suggest`** — given the most recent user prompt, runs harness
  `--route-only` and prints `recommended: /model <name>` with the call_type
  rationale. Read-only.

### Statusline

Two new segments after the existing CCC cost indicator:

- `routing<icon> <pct>%` — last-7d compliance rate from the violation log.
  Icon: ✓ ≥ 90%, ⚠ 70-89%, 🔴 < 70%.
- `OL→ $<n>/wk` — Sonnet-equivalent cost saved by L3 pre-compute, last 7 days.
  Hidden when `HARNESS_PRECOMPUTE` is off.

## Data flow

```
UserPromptSubmit
  │
  ├─[L1] harness-route.py
  │       └─▶ writes ~/.claude/state/harness-route.json
  │
  ├─[L2] ceiling-enforcer.py
  │       reads harness-route.json + hook input.session_model
  │       └─▶ writes ~/.claude/state/routing-violations-counter.jsonl
  │       └─▶ may exit 2 (hard block on 2-tier breach)
  │
  ├─[L3] delegation-precompute.py    (only if HARNESS_PRECOMPUTE=true)
  │       reads harness-route.json
  │       └─▶ dispatches via harness, injects [OL-precomputed] block
  │
  └─[existing] governance-router.py, budget-advisory.py, ...

Stop
  │
  ├─[L4] ccc-routing-violation.py    (existing, modified)
  ├─[L4] ccc-session-footer.py       (existing, modified)
  └─[L4] frequency-aggregator.py     (new)
```

## Components

| Component | Path | Role |
|---|---|---|
| harness-route.py | `~/.claude/hooks/harness-route.py` | L1 canonical decision cache |
| ceiling-enforcer.py | `~/.claude/hooks/ceiling-enforcer.py` | L2 hard-block / counter |
| delegation-precompute.py | `~/.claude/hooks/delegation-precompute.py` | L3 opt-in pre-compute |
| frequency-aggregator.py | `~/.claude/hooks/frequency-aggregator.py` | L4 daily / weekly digest |
| ccc-routing-violation.py | `~/.claude/hooks/ccc-routing-violation.py` | L4 — modified to read harness-route.json |
| ccc-session-footer.py | `~/.claude/hooks/ccc-session-footer.py` | L4 — adds compliance_pct |
| /delegate skill | `~/.claude/skills/delegate/SKILL.md` | L5 explicit delegation |
| /model-suggest skill | `~/.claude/skills/model-suggest/SKILL.md` | L5 read-only suggester |
| /ccc-digest skill | `~/.claude/skills/ccc-digest/SKILL.md` | L4 lazy on-click |
| statusline-command.sh | `~/.claude/statusline-command.sh` | extend with two segments |
| settings.json | `~/.claude/settings.json` | wire L1/L2/L3 + new Stop hook |

## Failure modes

- **Harness binary missing or hung.** L1 writes `degraded: true`; L2/L3 no-op
  except for soft logging; existing `governance-router.py` regex classifier
  remains as the safety net. No regression vs today.
- **L3 dispatch returns garbage.** L3 requires opt-in flag; off by default.
  When on, validates output is non-empty before injecting; otherwise silent
  skip.
- **L2 hard-block clipboard breakage.** Don't depend on the clipboard.
  Hook exits 2 with the message; the user re-types or re-pastes if needed.
  Future enhancement: persist the blocked prompt to
  `~/.claude/state/last-blocked-prompt.txt` and `/delegate` reads it as the
  default.
- **State file corruption.** All state files use atomic write (write to
  `<file>.tmp`, rename). Readers tolerate missing files.

## Testing strategy

- **Unit-level (offline):** Each hook reads stdin JSON, writes to a state
  dir parameterized by env var `CCC_STATE_DIR`. Tests pass synthetic prompts
  and assert the state file contents and exit code.
- **Integration:** Run `harness-route.py` against a known prompt; assert
  state file contents match `harness --route-only --json` output.
- **End-to-end:** Synthetic Claude session — script that submits 10 prompts
  with a forced Opus session model, asserts L2 blocks the 2-tier breaches,
  L3 pre-compute populates context only when env is set, and counter file
  ends at the expected size.
- **Soak:** Run for one week with telemetry on, compare 7-day cost/turn
  against the $0.12 baseline measured 2026-04-30. Target: ≤ $0.07 (within
  ~40% of historical baseline).

## Rollout

1. **Phase A — Visibility only.** Land L1 + L4 frequency aggregator + the
   `/ccc-digest` slash command. No blocking, no delegation. Run for 3 days
   to baseline the soft-violation rate.
2. **Phase B — Blocking.** Land L2 with hard-block on 2-tier breach. Verify
   block messages are clear and the `/delegate` relief valve works.
3. **Phase C — Delegation.** Land L3 (off by default), `/delegate`, and
   `/model-suggest`. Enable L3 via env var on a single workstation for one
   day; validate harness output quality on lookup-class prompts.
4. **Phase D — Statusline.** Add the two new segments. Make daily digest
   disable-able.

## Success metrics

- Per-turn cost (last 7 days) drops from $0.12 toward the $0.05 baseline.
- Opus turn share drops from 24% toward the 6% baseline for non-architecture
  call_types.
- Compliance rate visible in the statusline reaches and holds above 90%.
- `/delegate` is invoked at least 5x/week — meaning the relief valve is
  actually being used, not just present.

## Open questions

- None blocking. The `--no-clipboard` decision was made (don't depend on it).
  Daily digest can be quieted when the user is comfortable.
