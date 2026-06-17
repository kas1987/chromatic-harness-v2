import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { MemoryService } from "../../src/memory/memory-service";
import { SimpleEmbeddingProvider } from "../../src/memory/simple-embedding-provider";
import type { MemoryStore } from "../../src/memory/memory-store";
import type { MemoryItem } from "../../src/memory/memory-types";
import { agentId, projectId, userId, sessionId } from "../../src/memory/ids";

// Mock MemoryStore for testing without native SQL bindings
function createMockMemoryStore(): MemoryStore {
  const memories: Map<string, MemoryItem> = new Map();
  const embeddings: Map<string, Float32Array> = new Map();

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

describe("Memory Service", () => {
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

  it("createMemory stores a memory item with embedding", async () => {
    const ctx = {
      agentId: agentId("test-agent"),
      agentRole: "system",
      projectId: projectId("test-project"),
      userId: userId("test-user"),
      trustLevel: 2 as const,
      sessionId: sessionId("test-session"),
      purpose: "other" as const,
    };

    const memory = await memoryService.createMemory(ctx, {
      text: "Test memory text",
      kind: "summary",
      sourceStepId: null,
      sensitivity: "internal",
    });

    expect(memory).toBeDefined();
    expect(memory.text).toBe("Test memory text");
    expect(memory.kind).toBe("summary");
    expect(memory.id).toBeDefined();
  });

  it("retrieveMemories returns empty array when no memories stored", async () => {
    const ctx = {
      agentId: agentId("test-agent"),
      agentRole: "system",
      projectId: projectId("test-project"),
      userId: userId("test-user"),
      trustLevel: 2 as const,
    };

    const results = await memoryService.retrieveMemories(ctx, "search query");
    expect(results).toEqual([]);
  });

  it("retrieveMemories returns stored memories", async () => {
    const taskCtx = {
      agentId: agentId("test-agent"),
      agentRole: "system",
      projectId: projectId("test-project"),
      userId: userId("test-user"),
      trustLevel: 2 as const,
      sessionId: sessionId("test-session"),
      purpose: "other" as const,
    };

    const memory = await memoryService.createMemory(taskCtx, {
      text: "Important: use async/await for all IO",
      kind: "summary",
      sourceStepId: null,
      sensitivity: "internal",
    });

    const agentCtx = {
      agentId: agentId("test-agent"),
      agentRole: "system",
      projectId: projectId("test-project"),
      userId: userId("test-user"),
      trustLevel: 2 as const,
    };

    const results = await memoryService.retrieveMemories(agentCtx, "async await");

    expect(results).toHaveLength(1);
    expect(results[0].id).toBe(memory.id);
  });

  it("retrieveMemories can store agent-private memories", async () => {
    const taskCtx = {
      agentId: agentId("creator-agent"),
      agentRole: "system",
      projectId: projectId("test-project"),
      userId: userId("test-user"),
      trustLevel: 2 as const,
      sessionId: sessionId("test-session"),
      purpose: "other" as const,
    };

    const memory = await memoryService.createMemory(taskCtx, {
      text: "Private agent memory",
      kind: "summary",
      sourceStepId: null,
      sensitivity: "internal",
      scopeOverride: "agent_private",
    });

    // Creator agent can retrieve their own private memory
    const results = await memoryService.retrieveMemories(
      taskCtx,
      "private agent memory"
    );

    expect(results).toHaveLength(1);
    expect(results[0].scope).toBe("agent_private");
  });

  it("retrieveMemories respects minScore threshold", async () => {
    const taskCtx = {
      agentId: agentId("test-agent"),
      agentRole: "system",
      projectId: projectId("test-project"),
      userId: userId("test-user"),
      trustLevel: 2 as const,
      sessionId: sessionId("test-session"),
      purpose: "other" as const,
    };

    await memoryService.createMemory(taskCtx, {
      text: "Machine learning model training",
      kind: "summary",
      sourceStepId: null,
      sensitivity: "internal",
    });

    const agentCtx = {
      agentId: agentId("test-agent"),
      agentRole: "system",
      projectId: projectId("test-project"),
      userId: userId("test-user"),
      trustLevel: 2 as const,
    };

    // Use very high threshold - should get no results
    const results = await memoryService.retrieveMemories(agentCtx, "database", {
      minScore: 0.95,
    });

    expect(results).toHaveLength(0);
  });

  it("retrieveMemories respects maxItems limit", async () => {
    const taskCtx = {
      agentId: agentId("test-agent"),
      agentRole: "system",
      projectId: projectId("test-project"),
      userId: userId("test-user"),
      trustLevel: 2 as const,
      sessionId: sessionId("test-session"),
      purpose: "other" as const,
    };

    // Create 10 memories
    for (let i = 0; i < 10; i++) {
      await memoryService.createMemory(taskCtx, {
        text: `Memory ${i}: important context about the system`,
        kind: "summary",
        sourceStepId: null,
        sensitivity: "internal",
      });
    }

    const agentCtx = {
      agentId: agentId("test-agent"),
      agentRole: "system",
      projectId: projectId("test-project"),
      userId: userId("test-user"),
      trustLevel: 2 as const,
    };

    // Request only 3 items
    const results = await memoryService.retrieveMemories(agentCtx, "system", {
      maxItems: 3,
    });

    expect(results.length).toBeLessThanOrEqual(3);
  });
});
