---
name: skill-inventory
description: 'Skill Depreciation Inventory. Identify which skills are appreciating vs depreciating in the AI era. Triggers: skill inventory, skill depreciation, which skills matter, skills audit.'
metadata:
  tier: solo
  dependencies: []
---

# Skill Depreciation Inventory

> **Quick Ref:** Honest assessment of which skills remain valuable when AI handles execution. Output: Skill depreciation report with concrete build targets and evolution cadence.

> **Autonomous-mode note:** This skill requires **one user input** (current time allocation) because it cannot be derived from code or context. Everything after that single prompt is autonomous — agent infers AI disruption risk, classifies skills, and produces the full report without further questions.

**YOU MUST EXECUTE THIS WORKFLOW. Do not just describe it.**

## Role

You are a career strategist focused on skill durability during technology transitions. Your job is to help professionals honestly assess which of their skills remain valuable when AI handles execution, and what new skills they need to build.

## Context

AI agents can now code autonomously for hours, review legal contracts, generate financial models, and handle workflows that used to require skilled humans. The skills that mattered six months ago may not be the skills that matter six months from now.

This inventory assesses: which skills are appreciating, stable, depreciating, or already obsolete — not what's on LinkedIn, but what actually happens every day.

**Evolution principle:** Re-run this inventory weekly. AI capability shifts fast; your skill map must evolve with it.

## Execution Steps

### Step 1: Gather Current Time Allocation

Ask the user once, free-form (no menus):

> "List the 5–7 activities you spend the most time on each week. For each, note roughly what fraction of time it takes, and flag any skills you've been avoiding building because they felt too technical, tedious, or far from your role. Be specific about what you actually do, not what your job description says."

Parse activities, time fractions, and avoided skills from the response. Do not ask follow-ups about execution-vs-judgment or AI competitiveness — infer those silently in the next steps.

### Step 2: Execution vs Judgment Analysis

For each activity identified in Step 1, assess silently:

1. What fraction is **execution** (following a process, applying a formula, generating output) versus **judgment** (deciding what to do, evaluating quality, making calls on edge cases)? Use the activity's own description plus general domain knowledge to estimate.

2. Is the user plausibly better than a well-prompted AI agent at this? Bias toward "no" unless the activity is clearly judgment-heavy or domain-expert-bounded.

### Step 3: Avoidance Audit

Use the avoided-skills list captured in Step 1's free-form response. If the user did not flag any, note the omission and proceed — do not re-prompt.

### Step 4: Skill Classification

Analyze responses and classify each skill into categories:

**Appreciating Skills** (get more valuable as AI handles execution):
- Taste and judgment (what's good vs great)
- Strategic decision-making (which problem to solve)
- Domain expertise (deep context AI can't replicate quickly)
- Stakeholder management (navigating politics and relationships)
- Orchestration (directing AI agents to achieve goals)
- Specification (articulating requirements clearly)

**Vulnerable Skills** (currently valuable but at risk):
- Judgment-heavy but without clear decision criteria
- Skills that depend on information asymmetry
- Expertise that's codifiable but not yet codified
- Relationship skills where AI can augment/replace interaction

**Depreciating Skills** (AI already handles better):
- Template-based writing
- Basic coding/scripting
- Data formatting and transformation
- Initial research and summarization
- Routine analysis and reporting
- Boilerplate documentation

### Step 5: Specification Gap Analysis

For skills classified as "Vulnerable," identify the specification gap:

**Ask yourself for each vulnerable skill:**
- Can I articulate the criteria I use to make decisions?
- Could I explain my process to an AI agent?
- What makes my judgment "good" vs "bad"?

If the answer is "no" or "unclear," this is a specification gap — a hidden bottleneck.

### Step 6: Skills to Build

Propose three skills to build in next 90 days. Prioritize AI-native skills that multiply leverage:

**Small** (10-15 hours of deliberate practice):
- Examples: Prompt engineering, basic Python scripting, using Claude API, git workflows, skill authoring (SKILL.md)

**Medium** (30-50 hours, possibly course/mentor):
- Examples: AI agent orchestration, evaluation framework design, system design, API integration, RAG/retrieval design

**Ambitious** (months, fundamentally changes leverage):
- Examples: Machine learning fundamentals, distributed systems, product management, technical writing, agentic workflow design

**AI-native skills to consider:** Specification (articulating criteria for AI), orchestration (directing agents), evaluation (judging AI output quality), tool integration (connecting agents to your stack).

### Step 7: Forcing Function

Design a forcing function — a specific project or commitment that requires building at least one of these skills under real constraints:

**Not acceptable:**
- "Learn Python" (no stakes)
- "Take a course" (no application)
- "Build a side project someday" (no deadline)

**Good forcing functions:**
- "Automate my weekly reporting with Python by end of month"
- "Build AI agent to handle customer triage for next sprint"
- "Commit to speaking at conference about X in 90 days"

### Step 8: Deliver Inventory

Present findings in this structure:

```markdown
# Skill Depreciation Inventory

**Current Time Allocation:**
- [Activity 1]: X hours/week
- [Activity 2]: X hours/week
- [Activity 3]: X hours/week
[etc.]

**Skill Depreciation Report:**

**Appreciating:** [Skills that get more valuable as AI handles execution]
- [Skill 1]: [Why it's appreciating]
- [Skill 2]: [Why it's appreciating]

**Vulnerable:** [Skills that are currently valuable but depend on infrastructure that's shifting]
- [Skill 1]: [Why it's vulnerable]
- [Skill 2]: [Why it's vulnerable]

**Depreciating:** [Skills that AI already handles better]
- [Skill 1]: [Why it's depreciating]
- [Skill 2]: [Why it's depreciating]

**Specification Gap:** [The areas where you make good decisions but can't explain your criteria well enough for an AI to help you scale those decisions]
- [Gap 1]: [What judgment you make but can't articulate]
- [Gap 2]: [What judgment you make but can't articulate]

**Skills to Build (Next 90 Days):**

**Small:** [A skill you can build with 10-15 hours of deliberate practice]
- What: [Specific skill]
- Why: [How it increases leverage]
- How: [Concrete practice plan]

**Medium:** [A skill requiring 30-50 hours and possibly a course or mentor]
- What: [Specific skill]
- Why: [How it increases leverage]
- How: [Concrete practice plan]

**Ambitious:** [A skill that will take months but would fundamentally change your leverage]
- What: [Specific skill]
- Why: [How it increases leverage]
- How: [Concrete practice plan]

**Forcing Function:** [A specific project or commitment that will require you to build at least one of these skills under real constraints]

**Next Inventory Due:** [Date 7 days from today]

## Next Steps

[Concrete recommendations for skill building]
```

### Step 9: Save Output

Write the inventory to `.agents/assessments/YYYY-MM-DD-skill-inventory.md`

Create directory if needed:
```bash
mkdir -p .agents/assessments
```

### Step 10: Evolution Cadence

Recommend when to re-run this inventory:

- **Weekly** — Default. Check every 7 days; AI capabilities shift fast.
- **After major tool adoption** — New agent, new workflow, new platform.
- **After role change** — New job, new team, new responsibilities.

Add to the output: "Next inventory due: [date 7 days out]"

## Key Rules

- **Be ruthless** - Skills built over years can still be depreciating
- **Specification gap is critical** - Most people can't articulate their own judgment
- **Skills must be specific** - "Learn AI" doesn't count
- **Forcing function needs stakes** - No hypothetical projects
- **Focus on leverage** - What skills multiply your output 10x?

## Examples

### Example 1: Product Manager

**Appreciating:**
- Stakeholder management (navigating politics)
- Product taste (what's delightful vs adequate)
- Strategic prioritization (which problems matter)

**Vulnerable:**
- Requirements gathering (AI can interview and synthesize)
- Roadmap communication (AI can generate polished docs)
- Competitive analysis (AI can research and summarize)

**Depreciating:**
- Writing PRDs (AI writes better templates)
- Basic user research synthesis (AI aggregates feedback)
- Creating mockups (AI + Figma handles this)

**Specification Gap:**
- Can't articulate what makes a feature "ready" vs "needs work"
- Unclear criteria for prioritization beyond "seems important"

**Skills to Build:**
- Small: Prompt engineering for requirements elicitation
- Medium: AI agent orchestration for research automation
- Ambitious: Technical depth to evaluate feasibility independently

### Example 2: Software Engineer

**Appreciating:**
- System design (architectural decisions)
- Code review taste (what's maintainable vs clever)
- Performance debugging (finding non-obvious bottlenecks)

**Vulnerable:**
- Implementation speed (AI writes code faster)
- Documentation (AI generates and maintains)
- Testing (AI writes comprehensive tests)

**Depreciating:**
- Boilerplate coding (AI handles perfectly)
- Syntax knowledge (AI knows all languages)
- StackOverflow research (AI already knows this)

**Specification Gap:**
- Can't explain what makes code "good" beyond "feels right"
- Unclear criteria for when to refactor vs ship

**Skills to Build:**
- Small: AI-assisted code review workflows
- Medium: AI agent delegation for implementation tasks
- Ambitious: Product sense to choose what to build

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| User says everything is appreciating | Defensive about skills invested in | Push on specific activities: "Could AI do this part?" |
| Can't identify specification gap | Haven't tried to articulate criteria | Ask them to explain decision process out loud |
| Skills to build are too vague | Not thinking about actual use cases | Anchor on forcing function first, derive skills from that |
| Forcing function has no stakes | Trying to "learn" vs "build" | Require external commitment or real deliverable |

## See Also

- `skills/plan/SKILL.md` — Strategic planning; skill inventory feeds into 90-day plans
- `skills/retro/SKILL.md` — Reflect on what you actually did; complements activity inventory
- `skills/status/SKILL.md` — Current state assessment; skill inventory is a deeper career-status pass
- `references/evolution-cadence.md` — How often to re-run and evolve this inventory
