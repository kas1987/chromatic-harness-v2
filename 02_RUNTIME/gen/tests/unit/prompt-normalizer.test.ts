/**
 * Contract tests for {@link PromptNormalizer}: intent/scope classification, bypass ordering,
 * section matrix, and markdown shape. When changing `shouldBypass`, `classifyIntent`, or
 * `selectSections`, update expectations here and bump `PROMPT_NORMALIZER_VERSION` in source.
 */
import { describe, it, expect } from "vitest";
import { PromptNormalizer } from "../../src/prompting/prompt-normalizer";

describe("PromptNormalizer", () => {
  const normalizer = new PromptNormalizer();

  describe("Intent classification", () => {
    it("detects code intent for implementation requests", () => {
      const result = normalizer.normalize({ rawPrompt: "implement a new API endpoint for user authentication" });
      expect(result.intent).toBe("code");
    });

    it("detects code intent for refactoring requests", () => {
      const result = normalizer.normalize({ rawPrompt: "refactor the budget store to extract token counting" });
      expect(result.intent).toBe("code");
    });

    it("detects status intent for questions", () => {
      const result = normalizer.normalize({ rawPrompt: "what files have changed?" });
      expect(result.intent).toBe("status");
    });

    it("detects explore intent for research tasks", () => {
      const result = normalizer.normalize({ rawPrompt: "explore the existing memory service implementation" });
      expect(result.intent).toBe("explore");
    });

    it("detects manage intent for task/project work", () => {
      const result = normalizer.normalize({ rawPrompt: "break down this epic into subtasks" });
      expect(result.intent).toBe("manage");
    });

    it("detects dispatch intent for multi-agent orchestration", () => {
      const result = normalizer.normalize({ rawPrompt: "spawn agents to test all three database backends in parallel" });
      expect(result.intent).toBe("dispatch");
    });

    it("detects trigger intent for job submission", () => {
      const result = normalizer.normalize({ rawPrompt: "submit this workflow to the queue" });
      expect(result.intent).toBe("trigger");
    });

    it("detects schedule intent for recurring tasks", () => {
      const result = normalizer.normalize({ rawPrompt: "schedule a daily health check for the infrastructure" });
      expect(result.intent).toBe("schedule");
    });
  });

  describe("Scope inference", () => {
    it("infers simple scope for short prompts", () => {
      const result = normalizer.normalize({ rawPrompt: "fix typo in README" });
      expect(result.scope).toBe("simple");
    });

    it("infers medium scope for feature work", () => {
      const result = normalizer.normalize({ rawPrompt: "implement a new dashboard widget that displays real-time metrics" });
      expect(result.scope).toBe("medium");
    });

    it("infers complex scope for refactors", () => {
      const result = normalizer.normalize({ rawPrompt: "refactor the entire authentication layer to use OAuth 2.0 instead of session tokens across all three apps" });
      expect(result.scope).toBe("complex");
    });

    it("infers complex scope for architectural changes", () => {
      const result = normalizer.normalize({ rawPrompt: "redesign the system to use event-driven architecture" });
      expect(result.scope).toBe("complex");
    });
  });

  describe("Bypass conditions", () => {
    it("bypasses very short single-token prompts", () => {
      const result = normalizer.normalize({ rawPrompt: "go" });
      expect(result.bypassedReason).toBe("prompt too short (< 10 chars)");
      expect(result.structuredPrompt).toBe("go");
    });

    it("bypasses skill invocations (start with /)", () => {
      const result = normalizer.normalize({ rawPrompt: "/inject memory" });
      expect(result.bypassedReason).toBe("skill invocation (starts with /)");
      expect(result.structuredPrompt).toBe("/inject memory");
    });

    it("bypasses single words with no spaces", () => {
      const result = normalizer.normalize({ rawPrompt: "refactor" });
      expect(result.bypassedReason).toContain("single word");
    });

    it("bypasses acknowledgment commands", () => {
      const commands = ["yes", "no", "ok", "done", "thanks", "wait", "stop", "cancel"];
      commands.forEach((cmd) => {
        const result = normalizer.normalize({ rawPrompt: cmd });
        expect(result.bypassedReason).toContain("acknowledgment");
      });
    });

    it("bypasses pure information lookup questions", () => {
      const result = normalizer.normalize({ rawPrompt: "what is the API URL?" });
      expect(result.bypassedReason).toContain("information lookup");
    });

    it("bypasses quick commands", () => {
      const result = normalizer.normalize({ rawPrompt: "run tests" });
      expect(result.bypassedReason).toContain("quick command");
    });

    it("bypasses links and code pastes", () => {
      const result = normalizer.normalize({ rawPrompt: "https://example.com" });
      expect(result.bypassedReason).toContain("non-task input");
    });

    it("does not bypass substantial prompts", () => {
      const result = normalizer.normalize({ rawPrompt: "What is the status of the deployment and should we rollback?" });
      expect(result.bypassedReason).toBeUndefined();
      expect(result.intent).toBe("status");
    });
  });

  describe("Section selection matrix", () => {
    it("status intent uses role, goal, and output_format", () => {
      const result = normalizer.normalize({ rawPrompt: "Is the API running?" });
      expect(result.intent).toBe("status");
      expect(result.sectionsUsed).toEqual(["role", "goal", "output_format"]);
    });

    it("explore intent uses 5 sections including tools_methods", () => {
      const result = normalizer.normalize({ rawPrompt: "explore the memory service architecture" });
      expect(result.intent).toBe("explore");
      expect(result.sectionsUsed.length).toBe(5);
      expect(result.sectionsUsed).toContain("role");
      expect(result.sectionsUsed).toContain("tools_methods");
      expect(result.sectionsUsed).toContain("output_format");
    });

    it("manage intent uses 4 sections", () => {
      const result = normalizer.normalize({ rawPrompt: "organize these tickets into an epic" });
      expect(result.intent).toBe("manage");
      expect(result.sectionsUsed.length).toBe(4);
    });

    it("trigger intent uses 4 sections", () => {
      const result = normalizer.normalize({ rawPrompt: "trigger the deployment workflow" });
      expect(result.intent).toBe("trigger");
      expect(result.sectionsUsed.length).toBe(4);
      expect(result.sectionsUsed).toContain("risk_boundaries");
    });

    it("code simple scope uses 6 sections including tools_methods and decision_rules", () => {
      const result = normalizer.normalize({ rawPrompt: "fix typo" });
      expect(result.intent).toBe("code");
      expect(result.scope).toBe("simple");
      expect(result.sectionsUsed.length).toBe(6);
      expect(result.sectionsUsed).toContain("tools_methods");
      expect(result.sectionsUsed).toContain("decision_rules");
    });

    it("code medium scope uses 7 sections including decision_rules", () => {
      const result = normalizer.normalize({ rawPrompt: "implement a new feature for user authentication" });
      expect(result.intent).toBe("code");
      expect(result.scope).toBe("medium");
      expect(result.sectionsUsed.length).toBe(7);
      expect(result.sectionsUsed).toContain("tools_methods");
      expect(result.sectionsUsed).toContain("output_format");
      expect(result.sectionsUsed).toContain("decision_rules");
    });

    it("code complex scope uses all 8 sections", () => {
      const result = normalizer.normalize({ rawPrompt: "refactor the entire system architecture to support multi-tenancy" });
      expect(result.intent).toBe("code");
      expect(result.scope).toBe("complex");
      expect(result.sectionsUsed.length).toBe(8);
    });

    it("dispatch intent uses all 8 sections", () => {
      const result = normalizer.normalize({ rawPrompt: "spawn multiple agents to handle different aspects" });
      expect(result.intent).toBe("dispatch");
      expect(result.sectionsUsed.length).toBe(8);
    });
  });

  describe("Content generation", () => {
    it("includes role in all structured prompts", () => {
      const result = normalizer.normalize({ rawPrompt: "fix the database query performance" });
      expect(result.structuredPrompt).toContain("## Role");
    });

    it("includes goal in all structured prompts", () => {
      const result = normalizer.normalize({ rawPrompt: "optimize the search endpoint" });
      expect(result.structuredPrompt).toContain("## Goal");
    });

    it("includes constraints for code intent", () => {
      const result = normalizer.normalize({ rawPrompt: "implement new authentication" });
      expect(result.structuredPrompt).toContain("## Constraints");
      expect(result.structuredPrompt).toContain("conventional commit");
    });

    it("includes CLAUDE.md invariants in constraints", () => {
      const result = normalizer.normalize({ rawPrompt: "refactor the token counting logic" });
      expect(result.structuredPrompt).toContain("Never commit `.env`");
      expect(result.structuredPrompt).toContain("force-push to main");
    });

    it("includes risk boundaries for complex scope", () => {
      const result = normalizer.normalize({ rawPrompt: "redesign the entire architecture" });
      expect(result.structuredPrompt).toContain("## Risk Boundaries");
      expect(result.structuredPrompt).toMatch(/explicit approval|declare scope/i);
    });

    it("appends original request at the bottom", () => {
      const originalPrompt = "implement a new feature";
      const result = normalizer.normalize({ rawPrompt: originalPrompt });
      expect(result.structuredPrompt).toContain("**Original request:**");
      expect(result.structuredPrompt).toContain(originalPrompt);
    });

    it("includes memory context when provided", () => {
      const memories = ["Prior work on auth system (decision)", "Discussed token handling (feedback)"];
      const result = normalizer.normalize({
        rawPrompt: "update the authentication flow",
        memories,
      });
      expect(result.structuredPrompt).toContain("## Context");
      expect(result.structuredPrompt).toContain("Relevant prior context");
      expect(result.structuredPrompt).toContain("auth system");
    });

    it("includes project path in context when provided", () => {
      const result = normalizer.normalize({
        rawPrompt: "implement feature",
        projectPath: "D:/.04_Prism/Image-Prism",
      });
      expect(result.structuredPrompt).toContain("**Working directory:**");
      expect(result.structuredPrompt).toContain("Image-Prism");
    });
  });

  describe("Tool method guidance", () => {
    it("includes tool preferences for code intent by scope", () => {
      const simple = normalizer.normalize({ rawPrompt: "tweak the log line for errors" });
      expect(simple.scope).toBe("simple");
      expect(simple.structuredPrompt).toContain("## Tools & Methods");
      expect(simple.structuredPrompt).toContain("Read/Glob/Grep");

      const medium = normalizer.normalize({ rawPrompt: "refactor the database layer" });
      expect(medium.scope).toBe("medium");
      expect(medium.structuredPrompt).toContain("## Tools & Methods");
      expect(medium.structuredPrompt).toMatch(/LSP|type errors/i);
    });

    it("specifies worktree usage for complex refactors", () => {
      const result = normalizer.normalize({ rawPrompt: "comprehensive refactor of the authentication system" });
      expect(result.structuredPrompt).toContain("git worktree");
    });

    it("guides exploration methods for explore intent", () => {
      const result = normalizer.normalize({ rawPrompt: "explore the codebase for NSFW patterns" });
      expect(result.structuredPrompt).toContain("## Tools & Methods");
      expect(result.structuredPrompt).toContain("Grep");
    });
  });

  describe("Output format guidance", () => {
    it("specifies code output for code intent", () => {
      const result = normalizer.normalize({ rawPrompt: "implement authentication" });
      expect(result.structuredPrompt).toContain("## Output Format");
      expect(result.structuredPrompt).toContain("code");
    });

    it("specifies bullet points for explore intent", () => {
      const result = normalizer.normalize({ rawPrompt: "explore the architecture" });
      expect(result.structuredPrompt).toContain("Bullet-point");
    });

    it("specifies structured markdown for status intent", () => {
      const result = normalizer.normalize({ rawPrompt: "What is the status of the deployment?" });
      expect(result.structuredPrompt).toContain("## Output Format");
      expect(result.structuredPrompt).toContain("Structured markdown");
    });
  });

  describe("Decision rules", () => {
    it("includes decision rules in structured prompts", () => {
      const result = normalizer.normalize({ rawPrompt: "implement a feature and refactor the module" });
      expect(result.structuredPrompt).toContain("## Decision Rules");
      expect(result.structuredPrompt).toContain("ambiguous");
    });

    it("guides ambiguity handling for all intents", () => {
      const result = normalizer.normalize({ rawPrompt: "refactor something" });
      expect(result.structuredPrompt).toContain("minimal-scope");
    });
  });

  describe("Structured prompt format", () => {
    it("outputs valid markdown with section headings", () => {
      const result = normalizer.normalize({ rawPrompt: "implement a new endpoint" });
      expect(result.structuredPrompt).toMatch(/^## [A-Z]/m);
    });

    it("separates sections with blank lines", () => {
      const result = normalizer.normalize({ rawPrompt: "refactor the auth system" });
      expect(result.structuredPrompt).toContain("\n\n## ");
    });

    it("always ends with the original request", () => {
      const prompt = "do something important";
      const result = normalizer.normalize({ rawPrompt: prompt });
      expect(result.structuredPrompt).toMatch(new RegExp(`${prompt}$`));
    });

    it("separates structured content from original request with divider", () => {
      const result = normalizer.normalize({ rawPrompt: "implement a feature" });
      expect(result.structuredPrompt).toContain("---");
    });
  });

  describe("Edge cases", () => {
    it("handles prompts with special characters", () => {
      const result = normalizer.normalize({ rawPrompt: "fix bug with @decorator syntax & template literals" });
      expect(result.bypassedReason).toBeUndefined();
      expect(result.structuredPrompt).toContain("@decorator");
    });

    it("handles very long prompts", () => {
      const longPrompt = "A".repeat(2000);
      const result = normalizer.normalize({ rawPrompt: longPrompt });
      expect(result.bypassedReason).toBeUndefined();
      expect(result.intent).toBe("code");
    });

    it("handles prompts with newlines", () => {
      const multilinePrompt = "implement feature\nthat does X\nand also Y";
      const result = normalizer.normalize({ rawPrompt: multilinePrompt });
      expect(result.bypassedReason).toBeUndefined();
      expect(result.structuredPrompt).toContain(multilinePrompt);
    });

    it("handles empty memories array gracefully", () => {
      const result = normalizer.normalize({
        rawPrompt: "implement feature",
        memories: [],
      });
      expect(result.bypassedReason).toBeUndefined();
      expect(result.structuredPrompt).toBeDefined();
    });

    it("handles undefined memories gracefully", () => {
      const result = normalizer.normalize({
        rawPrompt: "implement feature",
        memories: undefined,
      });
      expect(result.bypassedReason).toBeUndefined();
      expect(result.structuredPrompt).toBeDefined();
    });
  });
});
