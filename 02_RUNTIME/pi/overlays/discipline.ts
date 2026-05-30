// discipline.ts — harness overlay for roach-pi (synced by scripts/sync_pi_karpathy_overlay.py)
import type { AgentConfig } from "./agents.js";

const DISCIPLINE_AGENTS = new Set(["plan-worker", "worker"]);

export const KARPATHY_CANON_VERSION = "1";

export function isDisciplineAgent(name: string): boolean {
  return DISCIPLINE_AGENTS.has(name);
}

export const KARPATHY_RULES = `

## Engineering Discipline: Karpathy Rules (Auto-Injected)

You MUST follow these behavioral guardrails during implementation:

### Think Before Coding
- State assumptions explicitly; ask if uncertain before coding.
- If multiple interpretations exist, present them — do not pick silently.

### Simplicity First
- Minimum code that solves the problem; nothing speculative.
- No features, abstractions, or config knobs unless asked.

### Hard Gates
1. **Read before you write** — Never modify a file you haven't read first.
2. **Scope to the request** — Change only what was asked. No "while I'm here" improvements.
3. **Verify, don't assume** — If you think something is "probably" true, grep and check first.
4. **Define success before starting** — Know what "done" looks like before writing code.

### Rules
1. **Surgical Changes** — Minimum edit to achieve the goal. No opportunistic refactoring.
2. **Match Existing Patterns** — Follow the project's conventions, not your preferences.
3. **No Premature Abstraction** — Don't add factories, wrappers, or "extensible" patterns unless asked.
4. **No Defensive Paranoia** — Don't add null checks for guaranteed values or error handling for impossible scenarios.
5. **No Future-Proofing** — Solve today's problem. Don't solve problems that don't exist yet.

### Goal-Driven Execution
- Define verifiable success criteria before starting.
- Do not claim done without running the stated checks.

### Anti-Patterns (Never Do These)
- "While I'm here" refactoring of nearby code
- Adding error handling for scenarios that cannot occur
- Making code "extensible" or "future-proof" without being asked
- Improving type safety on code you weren't asked to change
- Adding comments that restate what the code does
`;

export function augmentAgentWithKarpathy(agent: AgentConfig | undefined): AgentConfig | undefined {
  if (!agent) return agent;
  return {
    ...agent,
    systemPrompt: agent.systemPrompt + KARPATHY_RULES,
  };
}
