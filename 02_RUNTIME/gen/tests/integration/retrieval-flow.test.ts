import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { MemoryService } from "../../src/memory/memory-service";
import { SimpleEmbeddingProvider } from "../../src/memory/simple-embedding-provider";
import type { MemoryStore } from "../../src/memory/memory-store";
import type { MemoryItem } from "../../src/memory/memory-types";
import { agentId, projectId, userId, sessionId } from "../../src/memory/ids";

function createMockMemoryStore(): MemoryStore {
  const memories: Map<string, MemoryItem> = new Map();
  const embeddings: Map<string, Float32Array> = new Map();
  const acls: Map<string, any[]> = new Map();

  return {
    createAndStoreMemoryFromStep: vi.fn(function (ctx, input) {
      const memory: MemoryItem = {
        id: `mem-${Math.random().toString(36).substr(2, 9)}` as any,
        projectId: ctx.projectId,
        ownerUserId: ctx.userId ?? null,
        authorAgentId: ctx.agentId,
        scope: input.scopeOverride || (ctx.agentRole === "architect" ? "team_scoped" : "agent_private"),
        kind: input.kind,
        text: input.text,
        sourceStepId: input.sourceStepId,
        taskPurpose: ctx.purpose || null,
        sensitivity: input.sensitivity || "internal",
        createdAt: new Date().toISOString(),
        lastUsedAt: null,
        expiresAt: null,
        provenanceJson: null,
      };
      memories.set(memory.id, memory);
      if (input.embedding) {
        embeddings.set(memory.id, input.embedding);
      }
      // Mock ACLs
      acls.set(memory.id, [
        { id: 1, memoryId: memory.id, subjectType: "agent", subjectId: ctx.agentId, canRead: true, canWrite: true },
      ]);
      return memory;
    }),
    getRecentCandidatesForProject: vi.fn((projectId, purpose, limit) => {
      return Array.from(memories.values())
        .filter((m) => !m.projectId || m.projectId === projectId)
        .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
        .slice(0, limit);
    }),
    filterAndRankForAgent: vi.fn((ctx, scoredCandidates, opts) => {
      return scoredCandidates
        .filter((c) => c.score >= (opts?.minScore ?? 0))
        .sort((a, b) => b.score - a.score)
        .slice(0, opts?.maxItems ?? 8)
        .map((c) => c.memory);
    }),
    getEmbedding: vi.fn((memoryId) => embeddings.get(memoryId) || null),
    close: vi.fn(),
  } as any;
}

describe("Retrieval Flow Integration", () => {
  let memoryStore: MemoryStore;
  let memoryService: MemoryService;

  beforeEach(() => {
    memoryStore = createMockMemoryStore();
    const embeddingProvider = new SimpleEmbeddingProvider();
    memoryService = new MemoryService(memoryStore, embeddingProvider);
  });

  afterEach(() => {
    memoryService.close();
  });

  it("End-to-end: store memory → query → retrieve with scoring and ACL filtering", async () => {
    // Step 1: Store multiple memories from agent
    const creatorCtx = {
      agentId: agentId("code-agent"),
      agentRole: "coder",
      projectId: projectId("myapp"),
      userId: userId("alice"),
      trustLevel: 1 as const,
      sessionId: sessionId("session-1"),
      purpose: "other" as const,
    };

    const mem1 = await memoryService.createMemory(creatorCtx, {
      text: "Fixed async/await timeout bug in database layer",
      kind: "summary",
      sourceStepId: 1,
      sensitivity: "internal",
    });

    const mem2 = await memoryService.createMemory(creatorCtx, {
      text: "Refactored error handling middleware to use proper try/catch",
      kind: "decision",
      sourceStepId: 2,
      sensitivity: "internal",
    });

    const mem3 = await memoryService.createMemory(creatorCtx, {
      text: "Added tests for authentication flow",
      kind: "summary",
      sourceStepId: 3,
      sensitivity: "internal",
    });

    // Step 2: Query for relevant memories
    const agentCtx = {
      agentId: agentId("code-agent"),
      agentRole: "coder",
      projectId: projectId("myapp"),
      userId: userId("alice"),
      trustLevel: 1 as const,
    };

    const results = await memoryService.retrieveMemories(agentCtx, "async await timeout", {
      maxItems: 5,
      minScore: 0.0, // Include all scores for testing
    });

    // Step 3: Verify results are ranked by relevance
    expect(results.length).toBeGreaterThan(0);
    expect(results.length).toBeLessThanOrEqual(5);

    // The most relevant memory should be about async/await
    expect(results[0].text).toContain("async/await");

    // Step 4: Verify scoring and filtering
    const lowScoreResults = await memoryService.retrieveMemories(
      agentCtx,
      "zebra banana potato",
      {
        minScore: 0.8, // High threshold filters out low-relevance items
      }
    );

    // With very specific query unlikely to match, should get fewer results
    expect(lowScoreResults.length).toBeLessThanOrEqual(results.length);
  });

  it("Private agent memories are filtered correctly", async () => {
    // Step 1: Agent A stores a private memory
    const agentACtx = {
      agentId: agentId("agent-a"),
      agentRole: "system",
      projectId: projectId("shared-project"),
      userId: userId("alice"),
      trustLevel: 2 as const,
      sessionId: sessionId("session-a"),
      purpose: "other" as const,
    };

    await memoryService.createMemory(agentACtx, {
      text: "Debugging notes for agent-a internal issue",
      kind: "summary",
      sourceStepId: 1,
      sensitivity: "internal",
      scopeOverride: "agent_private",
    });

    // Step 2: Agent B tries to retrieve
    const agentBCtx = {
      agentId: agentId("agent-b"),
      agentRole: "system",
      projectId: projectId("shared-project"),
      userId: userId("alice"),
      trustLevel: 2 as const,
    };

    const results = await memoryService.retrieveMemories(
      agentBCtx,
      "debugging notes agent-a"
    );

    // Agent B should not see Agent A's private memory
    expect(results).toHaveLength(0);
  });

  it("Team-scoped memories are shared across agents in same project", async () => {
    // Step 1: Agent A stores a team-scoped memory
    const agentACtx = {
      agentId: agentId("agent-a"),
      agentRole: "architect",
      projectId: projectId("team-project"),
      userId: userId("alice"),
      trustLevel: 2 as const,
      sessionId: sessionId("session-a"),
      purpose: "other" as const,
    };

    const teamMemory = await memoryService.createMemory(agentACtx, {
      text: "Architecture decision: use async patterns everywhere",
      kind: "decision",
      sourceStepId: 1,
      sensitivity: "internal",
      scopeOverride: "team_scoped",
    });

    // Step 2: Agent B queries for it
    const agentBCtx = {
      agentId: agentId("agent-b"),
      agentRole: "coder",
      projectId: projectId("team-project"),
      userId: userId("bob"),
      trustLevel: 1 as const,
    };

    const results = await memoryService.retrieveMemories(
      agentBCtx,
      "architecture decision async"
    );

    // Agent B should see Agent A's team-scoped memory
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe(teamMemory.id);
  });
});
