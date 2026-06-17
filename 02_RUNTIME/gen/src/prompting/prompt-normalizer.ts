/** Bumped when regex/heuristic classification logic changes (spans + docs). */
export const PROMPT_NORMALIZER_VERSION = "regex-v2";

/**
 * PromptNormalizer - Structures incoming prompts using the 8-layer Anthropic approach.
 *
 * Reframes raw user prompts into:
 * Role → Goal → Context → Constraints → Tools & Methods → Risk Boundaries → Output Format → Decision Rules
 *
 * Intent-aware: depth scales with task complexity (status question ≠ complex refactor).
 * Synchronous. Fail-open. Always appends raw prompt at the bottom.
 */

export type IntentClass = "code" | "explore" | "manage" | "status" | "dispatch" | "trigger" | "schedule";
export type ScopeLevel = "simple" | "medium" | "complex";
export type PromptSection = "role" | "goal" | "context" | "constraints" | "tools_methods" | "risk_boundaries" | "output_format" | "decision_rules";

export interface NormalizerInput {
  rawPrompt: string;
  memories?: string[];
  projectPath?: string;
}

export interface NormalizerOutput {
  structuredPrompt: string;
  intent: IntentClass;
  scope: ScopeLevel;
  sectionsUsed: PromptSection[];
  bypassedReason?: string;
}

/**
 * Intent classification using lightweight regex patterns (not LLM-based).
 * Reuses the taxonomy from Spectrum but as a pure function for independence.
 */
function classifyIntent(prompt: string): IntentClass {
  const lower = prompt.toLowerCase();

  // dispatch — agent spawning, multi-step orchestration
  if (/spawn|delegate|multi-(?:phase|step|part)|orchestrat|parallel agents?/i.test(lower)) {
    return "dispatch";
  }

  // schedule — cron jobs, recurring tasks (check before trigger)
  if (/schedule|cron|recurring|periodic|interval|daily|weekly|hourly/i.test(lower)) {
    return "schedule";
  }

  // trigger — job submission, workflow execution
  if (/trigger|submit.*job|queue|dispatch job|run.*job/i.test(lower)) {
    return "trigger";
  }

  // manage — task management, planning, project work
  if (/task|backlog|board|kanban|epic|story point|roadmap|sprint|milestone|plan|track|manage/i.test(lower)) {
    return "manage";
  }

  // status — questions, diagnostics, health checks (check before explore)
  if (/\?$|status|health|diagnose/i.test(lower)) {
    // Exclude "implement status" type phrases that are really code intent
    if (!/implement|add|create|build|refactor/i.test(lower)) {
      return "status";
    }
  }

  // explore — discovery, research, investigation
  if (/explore|investigate|research|discover|understand|analyze|review|audit|scan/i.test(lower)) {
    return "explore";
  }

  // code — default (refactor, fix, feature, implement, debug, optimize, etc.)
  return "code";
}

/**
 * Infer scope from prompt characteristics.
 * Simple heuristics, not accurate analysis of actual file changes (that's endpoint's job).
 */
function inferScope(prompt: string): ScopeLevel {
  const lower = prompt.toLowerCase();

  // Explicit complexity markers
  if (/complex|epic|system|architecture|redesign|overhaul|consolidat|large-scale|multi-|comprehensive|entire|full.*refactor/i.test(lower)) {
    return "complex";
  }

  // Medium complexity markers
  if (
    /\bimplement\b|refactor|rewrite|migrate|integrate|implement.*feature|add.*feature|build|new endpoint|update|modify|change.*system/i.test(
      lower,
    )
  ) {
    return "medium";
  }

  // Simple: short prompts (< 100 chars), single-word commands, typos, quick fixes
  if (prompt.length < 50) {
    return "simple";
  }

  // Default to medium if long
  return "medium";
}

/**
 * Determine which sections to include based on intent + scope.
 */
function selectSections(intent: IntentClass, scope: ScopeLevel): PromptSection[] {
  switch (intent) {
    case "status":
      return ["role", "goal", "output_format"];
    case "explore":
      return ["role", "goal", "context", "tools_methods", "output_format"];
    case "manage":
      return ["role", "goal", "constraints", "decision_rules"];
    case "trigger":
    case "schedule":
      return ["role", "goal", "risk_boundaries", "decision_rules"];
    case "dispatch":
      return ["role", "goal", "context", "constraints", "tools_methods", "risk_boundaries", "output_format", "decision_rules"];
    case "code":
      if (scope === "simple") {
        return ["role", "goal", "context", "constraints", "tools_methods", "decision_rules"];
      }
      if (scope === "medium") {
        return ["role", "goal", "context", "constraints", "tools_methods", "output_format", "decision_rules"];
      }
      return ["role", "goal", "context", "constraints", "tools_methods", "risk_boundaries", "output_format", "decision_rules"];
  }
}

/**
 * Check if the prompt should bypass structuring.
 * Order matters: specific patterns before broad ones (e.g. acknowledgments before generic "short").
 */
function shouldBypass(raw: string): string | undefined {
  const prompt = raw.trim();
  if (prompt.length === 0) {
    return "empty prompt";
  }

  // Skill invocations
  if (prompt.startsWith("/")) {
    return "skill invocation (starts with /)";
  }

  // Affirmations / one-token replies (before length heuristics so "yes" is not swallowed by "< 10 chars")
  if (/^(yes|no|ok|okay|done|thanks|wait|stop|cancel|skip|next|back)$/i.test(prompt)) {
    return "acknowledgment command";
  }

  // Links, code snippets, pastes — before "single word" so URLs are not treated as one token
  if (/^(https?:|file:|```|git\s|git@)/i.test(prompt)) {
    return "non-task input (link/code/paste)";
  }

  // Single token (no spaces): bypass short tokens; long unbroken strings are still normalized
  if (!prompt.includes(" ")) {
    if (prompt.length > 96) {
      return undefined;
    }
    if (prompt.length <= 2) {
      return "prompt too short (< 10 chars)";
    }
    return "single word (no spaces)";
  }

  // Trivial definition lookups only — long questions stay structured (status, deployment, etc.)
  if (
    /^(what|where|when|who|which)\s+(?:is|are|was|were|does|do)\s+.+\?$/i.test(prompt) &&
    prompt.length <= 36
  ) {
    return "pure information lookup question";
  }

  // Obvious one-liners — omit "fix" so short structured tasks like "fix typo" stay normalized
  const quickCmd = /^(check|run|show|list|get|find|view|look|read|see|grep|test)\s+\S.{0,40}$/i;
  if (quickCmd.test(prompt) && prompt.length <= 48) {
    return "quick command";
  }

  return undefined;
}

export class PromptNormalizer {
  private buildRole(intent: IntentClass): string {
    const baseRole = "You are a senior software engineer working in the D:/.04_Prism workspace. You have full autonomy under bypassPermissions mode; the Gen hook pipeline at localhost:43123 is the safety net.";

    switch (intent) {
      case "code":
        return baseRole;
      case "explore":
        return "You are a research assistant with access to file inspection, web search, and code analysis tools.";
      case "manage":
        return "You are a project manager. You have access to task creation, tracking, and cron scheduling tools.";
      case "status":
        return "You are a status reporter. Provide concise, structured status information.";
      case "dispatch":
        return baseRole + " You delegate work to sub-agents via spawn_agent or codex-team routing.";
      case "trigger":
      case "schedule":
        return "You are a pipeline operator. You trigger and monitor jobs via remote triggers and background commands.";
    }
  }

  private buildGoal(rawPrompt: string): string {
    // Extract the imperative core (first sentence, or full prompt if short)
    const firstDot = rawPrompt.indexOf(".");
    if (firstDot > 0 && firstDot < 150) {
      return rawPrompt.substring(0, firstDot + 1);
    }
    return rawPrompt;
  }

  private buildContext(memories?: string[], projectPath?: string): string {
    const parts: string[] = [];

    if (projectPath) {
      parts.push(`**Working directory:** ${projectPath}`);
    }

    if (memories && memories.length > 0) {
      parts.push("**Relevant prior context:**");
      memories.forEach((mem) => {
        parts.push(`• ${mem}`);
      });
    }

    return parts.length > 0 ? parts.join("\n") : "You are in the D:/.04_Prism workspace. Consult memory for context on recent work.";
  }

  private buildConstraints(intent: IntentClass, scope: ScopeLevel): string {
    const rules = [
      "Never commit `.env`, `.env.local`, keys, or tokens",
      "Never force-push to main/master without explicit instruction",
      "Always use conventional commit format (feat:, fix:, docs:, chore:)",
      "Gen service writes to `.env`, `*.pem`, `*.key` are blocked at hook level — do not attempt",
    ];

    if (scope === "complex") {
      rules.push("For mass file operations (> 10 files), declare scope in one sentence before proceeding");
      rules.push("For destructive operations (git reset --hard, rm -rf), state what will be lost and why");
    }

    if (intent === "code") {
      rules.push("Run `pnpm run ci:trunk` before PRs in Image-Prism");
    }

    return rules.map((r) => `• ${r}`).join("\n");
  }

  private buildToolsAndMethods(intent: IntentClass, scope: ScopeLevel): string {
    if (intent === "code") {
      const guidance: Record<ScopeLevel, string> = {
        simple: "Prefer Read/Glob/Grep before Write/Edit. Use Bash for one-liners only.",
        medium: "Use LSP for type errors before attempting edits. Run tests after changes. Check for impact on sister projects.",
        complex: "Use EnterPlanMode for architectural decisions. Use git worktrees for large refactors. Run full CI suite (pnpm run ci:trunk).",
      };
      return guidance[scope];
    }

    if (intent === "explore") {
      return "Use Grep for content search before Read. Use WebSearch for external docs. Citation required for all sources.";
    }

    if (intent === "manage") {
      return "Use TaskCreate to break down work. Use TaskUpdate to track progress. Use TaskList to prioritize.";
    }

    return "Choose the simplest tool that accomplishes the goal. Avoid over-engineering.";
  }

  private buildRiskBoundaries(scope: ScopeLevel): string {
    const guidance: Record<ScopeLevel, string> = {
      simple: "Safe — execute immediately without declaration. No confirmation needed.",
      medium: "Medium risk — declare scope in one sentence before executing. Confirm if affecting shared systems.",
      complex: "Critical — multi-step plan required. All destructive operations require explicit approval before proceeding.",
    };
    return guidance[scope];
  }

  private buildOutputFormat(intent: IntentClass): string {
    switch (intent) {
      case "code":
        return "Lead with the answer. Show code in blocks. Use diffs for changes. No trailing summaries.";
      case "explore":
        return "Bullet-point findings. Include source links. End with a summary paragraph.";
      case "manage":
      case "status":
        return "Structured markdown. Use tables for status. Emoji prefixes: ✓ done, → in-progress, ✗ blocked.";
      case "dispatch":
      case "trigger":
      case "schedule":
        return "Structured specification. Include: goal, files affected, success criteria, time estimate.";
    }
  }

  private buildDecisionRules(intent: IntentClass): string {
    const rules = ["When ambiguous, prefer the minimal-scope interpretation. Ask one clarifying question."];

    if (intent === "code") {
      rules.push("When two valid approaches exist, implement the simpler one. Note the alternative for future reference.");
    }

    if (intent === "dispatch") {
      rules.push("When delegating, always define success criteria and time estimate before spawning.");
    }

    if (intent === "trigger") {
      rules.push("When a job fails, diagnose the root cause. Do not retry blindly.");
    }

    return rules.map((r) => `• ${r}`).join("\n");
  }

  normalize(input: NormalizerInput): NormalizerOutput {
    const { rawPrompt, memories, projectPath } = input;

    // Check for bypass conditions
    const bypassedReason = shouldBypass(rawPrompt);
    if (bypassedReason) {
      return {
        structuredPrompt: rawPrompt,
        intent: "code",
        scope: "simple",
        sectionsUsed: [],
        bypassedReason,
      };
    }

    // Classify intent and scope
    const intent = classifyIntent(rawPrompt);
    const scope = inferScope(rawPrompt);
    const sections = selectSections(intent, scope);

    // Build structured prompt
    const parts: string[] = [];

    for (const section of sections) {
      let content: string = "";
      switch (section) {
        case "role":
          content = this.buildRole(intent);
          break;
        case "goal":
          content = this.buildGoal(rawPrompt);
          break;
        case "context":
          content = this.buildContext(memories, projectPath);
          break;
        case "constraints":
          content = this.buildConstraints(intent, scope);
          break;
        case "tools_methods":
          content = this.buildToolsAndMethods(intent, scope);
          break;
        case "risk_boundaries":
          content = this.buildRiskBoundaries(scope);
          break;
        case "output_format":
          content = this.buildOutputFormat(intent);
          break;
        case "decision_rules":
          content = this.buildDecisionRules(intent);
          break;
      }

      if (content) {
        const heading =
          section === "tools_methods"
            ? "Tools & Methods"
            : section
                .split("_")
                .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                .join(" ");
        parts.push(`## ${heading}\n${content}`);
      }
    }

    // Append separator and original request
    parts.push("---");
    parts.push(`**Original request:**\n${rawPrompt}`);

    return {
      structuredPrompt: parts.join("\n\n"),
      intent,
      scope,
      sectionsUsed: sections,
    };
  }
}
