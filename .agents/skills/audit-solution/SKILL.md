---
name: audit-solution
description: Use when a gap, feature, or tool has been identified and you need to check if an existing solution exists before building — before writing any implementation code, before /plan, before /rpi. Triggers on phrases like "before I build", "does something exist", "is there a library for", "should I build or use", "find me a solution for".
---

# Audit Solution

## Overview

Single-pass audit: search → evaluate → decide → commit. No sub-skills, no review loops, no generic dispatch chains. One agent, one pass, done in under 15 minutes.

**Core principle:** If a decision is clear, ship it. Only escalate when two candidates are within 10% of each other on the evaluation matrix.

---

## When to Use

- Gap identified, solution unknown
- About to start `/plan` or `/rpi` on something that might already exist
- User says "build X" and X sounds like a solved problem

**Skip this audit when:**
- Well-known library (React, Tailwind, Zustand) — just use it
- Feature is deeply custom to this codebase (no generic equivalent exists)
- Already audited in `.agents/audits/INDEX.md` (check first)

---

## The Process

**Time-box: 15 minutes max. Decisions > perfection.**

### Step 1 — Check INDEX.md first (30 seconds) ⚠️ DO THIS BEFORE ANYTHING ELSE

```bash
grep -i "<gap keyword>" ".agents/audits/INDEX.md"
```

If match found → read that file, done. **Do not search. Do not evaluate. Do not create a new file.** Never re-audit a decided gap.

If no match → continue to Step 2.

### Step 2 — Classify domain and open SEARCH_QUERIES.md (1 minute)

**Read `.agents/audits/SEARCH_QUERIES.md` now.** Find the matching domain section:
- File upload / drag-drop → "File Handling & Processing"
- State sync → "State Management & Sync"
- Images → "Image Processing & Computer Vision"
- DevOps → "DevOps & CI/CD"
- UI → "UI Components & Design System"

Copy the relevant query. **Do not web search yet.** GitHub search with the domain query comes first. Only fall back to web search if GitHub returns zero relevant results.

If no section matches → use: `"<gap term>" language:typescript stars:>100`

### Step 3 — Search (3 minutes)

Paste the domain query into GitHub search. Sort by stars, then by updated. Scan first page only.

**3 candidates max. Hard stop at 3 — even if more look relevant.**

"Be thorough" does not mean more candidates. Thorough means a well-filled evaluation matrix for 3 candidates, not a shallow matrix for 6.

### Step 4 — Rapid evaluation (5 minutes)

Score each candidate against defaults (override only if user specified custom criteria):

| Criterion | Default | Pass ✅ | Caution ⚠️ | Fail ❌ |
|-----------|---------|---------|------------|--------|
| License | MIT/Apache/ISC | Any of these | BSD/MPL | GPL/SSPL/proprietary |
| Last commit | <12 months | <6mo | 6-12mo | >12mo |
| Stars | 100+ (flexible for niche) | >500 | 100-500 | <100 |
| Customization cost | <20% fork | <10% | 10-20% | >20% |
| Mobile/web fit | Project-dependent | Native support | Adapter needed | Unsupported |

**Decision rules:**
- Any candidate with 0 ❌ and ≥3 ✅ → **INTEGRATE** (clear winner)
- All candidates have ≥1 ❌ → **BUILD or DEFER** (nothing fits)
- Two candidates score within 10% → **AMBIGUOUS** (see Escalation below)

### Step 5 — Write audit file (3 minutes)

Create `.agents/audits/YYYY-MM-DD-<gap-slug>.md` using `.agents/audits/TEMPLATE.md`.

Fill all sections. Decision section must include:
- Selected option + rationale (2-3 sentences)
- Integration method (dependency / fork / hybrid)
- 3-5 concrete next steps
- Any features to build on top

**Do not leave placeholder text.** Every field must be filled.

### Step 6 — Update INDEX.md (1 minute)

Append one row to the Audits & Decisions table in `.agents/audits/INDEX.md`:

```markdown
| YYYY-MM-DD | <Gap/Feature> | <Decision> | <Solution or N/A> | Evaluated | [Link](./<filename>.md) |
```

### Step 7 — Commit

```bash
git add ".agents/audits/YYYY-MM-DD-<gap-slug>.md" ".agents/audits/INDEX.md"
git commit -m "docs(audit): <gap-slug> → <decision> (<solution or custom>)"
```

Examples:
- `docs(audit): background-removal → integrate (replicate-bria-rmbg)`
- `docs(audit): state-sync → build (no suitable solution, too custom)`
- `docs(audit): pdf-export → defer (low priority, no urgency)`

---

## Ambiguity Escalation

Only escalate if two candidates score within 10% of each other AND the integration method differs (dep vs. fork). Otherwise, pick the one with better documentation.

**How to handle ambiguity:**
1. Note both candidates in the audit file under "Option A" and "Option B"
2. Add an "Ambiguity Note" section listing the tie-breaking factors
3. Ask the user one focused question: "Both X and Y fit. X is dependency-only, Y needs a fork. Which do you prefer?"
4. Do NOT spawn a reviewer agent. Do NOT run Superpowers loops.

---

## Model Guidance

This skill runs in the **current session** — no subagent dispatch needed for standard audits.

If you need to delegate (e.g., large number of gaps in batch):
- Use **haiku** for mechanical evaluation (Step 4 matrix scoring)
- Use **sonnet** only if gap is architecturally complex or ambiguity escalation is needed
- Never use **opus** for an audit

---

## Red Flags — Stop and Correct

If you notice any of these, stop and fix before continuing:

- **Evaluated 4+ candidates** — Delete the extra rows. Max is 3.
- **Skipped the INDEX.md grep** — Do it now, even mid-audit.
- **Used web search before SEARCH_QUERIES.md** — Acceptable if GitHub returned nothing. Otherwise, redo with domain query.
- **Left any `[TBD]` or `[fill in]`** — Fill it or delete the field.
- **INDEX.md not in the commit** — Amend the commit to add it.

## Rationalization Table (from RED baseline — tested 2026-04-02)

| Rationalization | Reality |
|----------------|---------|
| "The task says be thorough → I'll evaluate 4 candidates" | Thorough = quality of reasoning, not quantity of candidates. 3 max, always. |
| "I'll search GitHub and also check npm/web to be comprehensive" | Use SEARCH_QUERIES.md domain query first. Web search only if GitHub returns zero relevant results. |
| "I'll start searching, I can check INDEX.md later" | INDEX.md check is Step 1. If it's already decided, all search work is wasted. Do it first. |
| "More rows in the matrix = more credible decision" | 3 well-scored candidates > 6 half-scored ones. Depth beats breadth. |
| "I didn't find it in SEARCH_QUERIES.md so I'll web search" | Check all domain sections in SEARCH_QUERIES.md before falling back. Many queries apply across sections. |

---

## RED Baseline Results (tested 2026-04-02)

Subagent dispatched without skill on "drag-and-drop file upload" scenario with "be thorough" pressure.

**Violations observed:**
- Evaluated 4 candidates (react-dropzone, Uppy, Filepond, RDU) — exceeded 3-candidate limit
- Skipped INDEX.md check entirely — went straight to searching
- Used web search ("react-dropzone alternatives TypeScript 2026") before SEARCH_QUERIES.md
- 28 tool calls for a documentation task

**What held without the skill:**
- Clear decision made (no ambiguity inflation)
- Template fully filled (no placeholders)
- Both files committed in one commit
- Good rationale and concrete next steps

**Fixes applied:** Step 1 hardened with ⚠️ warning + "DO THIS BEFORE ANYTHING ELSE", SEARCH_QUERIES.md made mandatory in Step 2, "thorough ≠ more candidates" counter added, Red Flags section added, Rationalization Table added from observed failures.

---

## Superpowers Gap Comparison

Why this skill exists vs. Superpowers default:

| Concern | Superpowers | This Skill |
|---------|-------------|------------|
| Token cost | 3-5 agents per task | 1 pass inline |
| Review loops | Always: spec + quality + re-review | Only if ambiguous |
| Model selection | Not specified | haiku by default |
| Context loaded | Generic plan + full history | Only TEMPLATE.md + SEARCH_QUERIES.md |
| Sub-skill chaining | 4+ skills invoked | None |
| Time per audit | 15-30 min | 15 min max |

---

## See Also

- `.agents/audits/TEMPLATE.md` — Evaluation matrix to fill
- `.agents/audits/SEARCH_QUERIES.md` — Domain search queries
- `.agents/audits/INDEX.md` — Decision log (check before starting)
- `.agents/audits/README.md` — Full process guide

## Examples

### Evaluate a new npm library
```
/audit-solution axios vs node-fetch for HTTP client
```
Expected: Reads SEARCH_QUERIES.md, searches for comparisons, fills TEMPLATE.md evaluation matrix, writes decision to INDEX.md. Done in ≤15 min.

### Audit a proposed architectural change
```
/audit-solution migrating from REST to GraphQL for the API layer
```
Expected: Loads domain queries, researches trade-offs, scores against evaluation criteria, outputs recommendation with rationale.

### Check INDEX.md before starting
Always verify the decision hasn't already been made:
```bash
grep -i "axios\|fetch" .agents/audits/INDEX.md
```

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `TEMPLATE.md` not found | Audits directory not initialized | Run audit setup: create `.agents/audits/` and seed with TEMPLATE.md and SEARCH_QUERIES.md |
| Decision already in INDEX.md | Prior audit covered same topic | Read prior entry; only re-audit if context has significantly changed (new major version, etc.) |
| Research exceeds 15 min | Topic too broad | Narrow the scope: specific version comparison, specific use case, specific constraint |
| Recommendation unclear | Evaluation scores tied across criteria | Add a tiebreaker criterion (team familiarity, ecosystem momentum) and re-score |
| Superpowers spawns 3-5 agents for same task | Using wrong skill | Use `audit-solution` (1-pass inline) instead of generic superpowers for solution evaluation |
