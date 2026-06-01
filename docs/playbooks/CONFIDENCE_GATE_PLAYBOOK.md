# Confidence Gate Playbook

> Issue #81 / NW-RG-081. Implemented by `score_confidence()` / `confidence_band()`
> in `scripts/go_mode.py`. **Confidence scoring is required before any mutation.**

## Formula

Seven factors, each scored **0–100**, combined by fixed weights (sum = 1.0):

```
Confidence =
  Objective Clarity * 0.20 +
  Scope Clarity     * 0.20 +
  Evidence Quality  * 0.20 +
  Reversibility     * 0.10 +
  Tool Fit          * 0.10 +
  Risk Awareness    * 0.10 +
  Testability       * 0.10
```

Missing factors default to **50** (neutral) — an under-specified task cannot
score high by omission. Factors are estimated from queue-item metadata by
`estimate_factors()` (objective/title presence, acceptance-check count,
allowed-files scope, declared risk, stop-conditions, test mentions) or supplied
explicitly.

## Bands

| Score | Band | Behavior | May mutate |
|---:|---|---|:---:|
| 90–100 | `execute` | Execute normally within scope | yes |
| 75–89 | `execute_logged` | Execute with normal logging | yes |
| 60–74 | `reversible_only` | Execute only if reversible and low risk | yes |
| 40–59 | `plan_only` | Plan only; do not mutate | no |
| 0–39 | `halt` | Halt and escalate | no |

## Required record

Every mutation (or dispatch authorizing one) must record:

- the confidence **score**,
- the **seven factor values**, and
- the **band** and resulting action.

`go_mode.py` writes all three into `07_LOGS_AND_AUDIT/go_mode/latest.json` and
into the mission packet's `confidence` block, so the rationale is auditable.

## Relationship to the runtime DecisionMagnet

`02_RUNTIME/magnets/decision_magnet.py::decide_band()` maps a composite
confidence to the CMP runtime bands (90 proceed / 70 reversible / 50 self-heal /
<50 escalate) during live magnet processing. This playbook's 5-band table is the
**planning-time gate** used by GO-mode selection; both share the principle "no
mutation below ~60 without reversibility." Keep them aligned when either changes
(tracked against the dual-source-of-truth cleanup, issue #84).
