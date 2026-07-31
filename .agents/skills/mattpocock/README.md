# mattpocock/skills in Chromatic Harness v2

Local mirror of [mattpocock/skills](https://github.com/mattpocock/skills).
All skills are namespaced under `mattpocock-<skill>` to avoid collisions with existing AgentOps skills in this repo.

## Setup

Run once per repo before using the engineering skills:

```
mattpocock-setup-matt-pocock-skills
```

This configures the issue tracker mapping, triage labels, and domain-doc layout expected by the engineering skills.

## Design principles for harness v2

- **Small and composable**: Prefer one focused skill per turn rather than chaining multiple large skills.
- **Token-aware**: Use the tier table below to pick the cheapest skill that can answer the question.
- **Explicit triggers**: Let the user or bead spec name the skill; do not silently invoke `grill` or `research` unless asked.
- **Prefer local canon**: When a harness-specific skill exists (e.g., `audit-solution`, `heal-skill`), use it for repo-governance work; use mattpocock skills for generic engineering/productivity workflows.

## Workflow quick reference

| Harness phase | Recommended skill | Why |
|---------------|-------------------|-----|
| Starting a new feature or unsure what skill fits | `mattpocock-ask-matt` | Router to avoid token waste |
| Aligning on requirements before coding | `mattpocock-grill-with-docs` | Produces ADR/glossary as a side effect |
| Converting chat into a spec | `mattpocock-to-spec` | Cheap synthesis, no interview |
| Breaking a spec into tracer-bullet tickets | `mattpocock-to-tickets` | Creates blocking edges |
| Day-to-day implementation | `mattpocock-implement` + `mattpocock-tdd` | Spec-driven + red-green-refactor |
| Hard bug or performance regression | `mattpocock-diagnosing-bugs` | Structured diagnosis loop |
| Code review of a diff/PR/branch | `mattpocock-code-review` | Two-axis review in parallel sub-agents |
| Huge multi-session chunk of work | `mattpocock-wayfinder` | Shared map of decision tickets |
| Resolving merge/rebase conflicts | `mattpocock-resolving-merge-conflicts` | Never `--abort` |
| Research against primary sources | `mattpocock-research` | Background agent with citations |
| Teaching or handoff | `mattpocock-teach` / `mattpocock-handoff` | Compact, reusable |
| Triage of issues/PRs | `mattpocock-triage` | State-machine categorisation |

## Token governance tiers

| Tier | Approx tokens | Skills | Use pattern |
|------|---------------|--------|-------------|
| xs | < 300 | implement, resolving-merge-conflicts, grilling, grill-me, research | Default first-line, cheap to invoke |
| s | 300 - 800 | to-spec, prototype, tdd, migrate-to-shoehorn, edit-article, handoff, obsidian-vault, setup-pre-commit, scaffold-exercises, domain-modeling | Common single-turn skills |
| m | 800 - 1600 | codebase-design, improve-codebase-architecture, to-tickets, git-guardrails-claude-code, setup-matt-pocock-skills | Use when problem is scoped |
| l | 1600 - 2500 | code-review, diagnosing-bugs, triage, ask-matt, writing-great-skills, teach | Reserve for high-value sessions |
| xl | > 2500 | grill-with-docs, wayfinder | Use only when alignment is worth the cost |

## Skill catalog

### Engineering

| Skill | Tokens | Tier | Description |
|-------|--------|------|-------------|
| `mattpocock-ask-matt` | 2084 | l | Ask which skill or flow fits your situation. A router over the skills in this repo. disable-model-invocation: true |
| `mattpocock-code-review` | 1707 | l | Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes — Standards (does the code follow this repo's documented coding standards?) and Spec (does the code match what the originating issue/PRD asked for?). Runs both reviews in parallel sub-agents and reports them side by side. Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to "review since X". |
| `mattpocock-codebase-design` | 1650 | l | Shared vocabulary for designing deep modules. Use when the user wants to design or improve a module's interface, find deepening opportunities, decide where a seam goes, make code more testable or AI-navigable, or when another skill needs the deep-module vocabulary. |
| `mattpocock-diagnosing-bugs` | 2168 | l | Diagnosis loop for hard bugs and performance regressions. Use when the user says "diagnose"/"debug this", or reports something broken/throwing/failing/slow. |
| `mattpocock-domain-modeling` | 875 | m | Build and sharpen a project's domain model. Use when the user wants to pin down domain terminology or a ubiquitous language, record an architectural decision, or when another skill needs to maintain the domain model. |
| `mattpocock-grill-with-docs` | 63 | xs | A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go. disable-model-invocation: true |
| `mattpocock-implement` | 112 | xs | "Implement a piece of work based on a spec or set of tickets." disable-model-invocation: true |
| `mattpocock-improve-codebase-architecture` | 1528 | m | Scan a codebase for deepening opportunities, present them as a visual HTML report, then grill through whichever one you pick. disable-model-invocation: true |
| `mattpocock-prototype` | 706 | s | Build a throwaway prototype to answer a design question. Use when the user wants to sanity-check whether a state model or logic feels right, or explore what a UI should look like. |
| `mattpocock-research` | 203 | xs | Investigate a question against high-trust primary sources and capture the findings as a Markdown file in the repo. Use when the user wants a topic researched, docs or API facts gathered, or reading legwork delegated to a background agent. |
| `mattpocock-resolving-merge-conflicts` | 234 | xs | "Use when you need to resolve an in-progress git merge/rebase conflict." |
| `mattpocock-setup-matt-pocock-skills` | 1761 | l | Configure this repo for the engineering skills — set up its issue tracker, triage label vocabulary, and domain doc layout. Run once before first use of the other engineering skills. disable-model-invocation: true |
| `mattpocock-tdd` | 812 | m | Test-driven development. Use when the user wants to build features or fix bugs test-first, mentions "red-green-refactor", or wants integration tests. |
| `mattpocock-to-spec` | 787 | s | Turn the current conversation into a spec and publish it to the project issue tracker — no interview, just synthesis of what you've already discussed. disable-model-invocation: true |
| `mattpocock-to-tickets` | 1453 | m | Break a plan, spec, or the current conversation into a set of tracer-bullet tickets, each declaring its blocking edges, published to the configured tracker — edges as text in one file per ticket locally, or native blocking links on a real tracker. disable-model-invocation: true |
| `mattpocock-triage` | 1672 | l | Move issues and external PRs through a state machine of triage roles — categorise, verify, grill if needed, and write agent-ready briefs. disable-model-invocation: true |
| `mattpocock-wayfinder` | 3007 | xl | Plan a huge chunk of work — more than one agent session can hold — as a shared map of decision tickets on your issue tracker, and resolve them one at a time until the way to the destination is clear. disable-model-invocation: true |

### Productivity

| Skill | Tokens | Tier | Description |
|-------|--------|------|-------------|
| `mattpocock-grill-me` | 38 | xs | A relentless interview to sharpen a plan or design. disable-model-invocation: true |
| `mattpocock-grilling` | 214 | xs | Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases. |
| `mattpocock-handoff` | 224 | xs | Compact the current conversation into a handoff document for another agent to pick up. argument-hint: "What will the next session be used for?" disable-model-invocation: true |
| `mattpocock-teach` | 2412 | l | Teach the user a new skill or concept, within this workspace. disable-model-invocation: true argument-hint: "What would you like to learn about?" |
| `mattpocock-writing-great-skills` | 2374 | l | Reference for writing and editing skills well — the vocabulary and principles that make a skill predictable. disable-model-invocation: true |

### Misc

| Skill | Tokens | Tier | Description |
|-------|--------|------|-------------|
| `mattpocock-git-guardrails-claude-code` | 602 | s | Set up Claude Code hooks to block dangerous git commands (push, reset --hard, clean, branch -D, etc.) before they execute. Use when user wants to prevent destructive git operations, add git safety hooks, or block git push/reset in Claude Code. |
| `mattpocock-migrate-to-shoehorn` | 728 | s | Migrate test files from `as` type assertions to @total-typescript/shoehorn. Use when user mentions shoehorn, wants to replace `as` in tests, or needs partial test data. |
| `mattpocock-scaffold-exercises` | 924 | m | Create exercise directory structures with sections, problems, solutions, and explainers that pass linting. Use when user wants to scaffold exercises, create exercise stubs, or set up a new course section. |
| `mattpocock-setup-pre-commit` | 588 | s | Set up Husky pre-commit hooks with lint-staged (Prettier), type checking, and tests in the current repo. Use when user wants to add pre-commit hooks, set up Husky, configure lint-staged, or add commit-time formatting/typechecking/testing. |

### Personal

| Skill | Tokens | Tier | Description |
|-------|--------|------|-------------|
| `mattpocock-edit-article` | 192 | xs | Edit and improve articles by restructuring sections, improving clarity, and tightening prose. Use when user wants to edit, revise, or improve an article draft. disable-model-invocation: true |
| `mattpocock-obsidian-vault` | 392 | s | Search, create, and manage notes in the Obsidian vault with wikilinks and index notes. Use when user wants to find, create, or organize notes in Obsidian. |

## Collision notes with existing AgentOps/harness skills

- `mattpocock-implement` is a generic implementation driver. Prefer `agentops:implement` or `implement` (r0) when the work is tied to a bead and must follow harness CI/governance gates.
- `mattpocock-research` is for general research. Prefer `agentops:research` or `research` (r0) for knowledge-mining tied to the .agents wiki.
- `mattpocock-triage` is for issue/PR triage. Do not confuse with `agentops:beads` or `bd` workflows; use it to categorise inbound items before creating beads.
- `mattpocock-handoff` is a generic handoff writer. Continue to use the harness `12_HANDOFFS/SESSION_COMPACT.md` protocol and `.agents/handoffs/latest.json` for cross-session continuity.
- `mattpocock-code-review` does Standards + Spec review. Use it for branch/PR reviews; use `review` (r0) or `agentops:review` for agent-generated PR validation.

## Maintenance

Upstream: `https://github.com/mattpocock/skills`. To refresh this mirror:

```bash
cd C:\temp\mattpocock-skills
git pull
powershell -ExecutionPolicy Bypass -File C:\temp\copy_mattpocock_skills.ps1
```

After refresh, regenerate this README and run `mattpocock-writing-great-skills` if any local skill adaptations are needed.
