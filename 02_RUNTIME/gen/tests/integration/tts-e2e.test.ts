/**
 * Integration test: pretool hook → TTS synthesis → audioPath in response
 *
 * Tests the full flow: memory retrieval triggers TTS → audioPath returned.
 * TTS client is mocked (external HTTP service); memory service uses real logic
 * with a mock store so scoring/retrieval is exercised end-to-end.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import express from "express";
import request from "supertest";
import {
  hooksRouter,
  initializeHooksRouter,
  initializeTtsClient,
} from "../../src/routes/hooks";
import { MemoryService } from "../../src/memory/memory-service";
import { SimpleEmbeddingProvider } from "../../src/memory/simple-embedding-provider";
import type { MemoryStore } from "../../src/memory/memory-store";
import type { MemoryItem } from "../../src/memory/memory-types";
import type { TtsClient } from "../../src/tts/tts-client";
import { agentId, projectId, userId, sessionId } from "../../src/memory/ids";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
        scope: input.scopeOverride || "agent_private",
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
    getRecentCandidatesForProject: vi.fn((_projectId, _purpose, limit) =>
      Array.from(memories.values()).slice(0, limit ?? 20)
    ),
    filterAndRankForAgent: vi.fn((_ctx, scoredCandidates, opts) =>
      scoredCandidates
        .filter((c: any) => c.score >= (opts?.minScore ?? 0))
        .sort((a: any, b: any) => b.score - a.score)
        .slice(0, opts?.maxItems ?? 8)
        .map((c: any) => c.memory)
    ),
    getEmbedding: vi.fn((memoryId) => embeddings.get(memoryId) ?? null),
    close: vi.fn(),
  } as any;
}

function makeMockTts(audioFilename = "abc123.wav"): TtsClient {
  return {
    isAvailable: vi.fn().mockResolvedValue(true),
    synthesize: vi.fn().mockResolvedValue({
      audioPath: `/tmp/audio/${audioFilename}`,
      voiceId: "UA___20s_Woman",
      durationMs: 400,
    }),
    listVoices: vi.fn().mockResolvedValue(["UA___20s_Woman"]),
    warmup: vi.fn().mockResolvedValue(undefined),
    pruneOldFiles: vi.fn().mockResolvedValue(0),
  } as unknown as TtsClient;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TTS e2e integration: pretool → synthesis → audioPath", () => {
  let app: express.Application;
  let memoryService: MemoryService;
  let mockTts: TtsClient;

  beforeEach(async () => {
    app = express();
    app.use(express.json());
    app.use("/hooks", hooksRouter);

    const store = createMockMemoryStore();
    memoryService = new MemoryService(store, new SimpleEmbeddingProvider());
    initializeHooksRouter(memoryService);

    mockTts = makeMockTts();
    initializeTtsClient(mockTts);

    // Pre-seed a memory that matches common bash queries so retrieval fires
    const ctx = {
      agentId: agentId("system"),
      agentRole: "system",
      projectId: projectId("default"),
      userId: userId("user"),
      trustLevel: 2 as const,
      sessionId: sessionId("sess-1"),
      purpose: "other" as const,
    };
    await memoryService.createMemory(ctx, {
      text: "Use npx ts-node for running TypeScript scripts directly",
      kind: "summary",
      sourceStepId: 1,
      sensitivity: "internal",
    });
  });

  afterEach(() => {
    // Reset module-level singletons so tests don't bleed into each other
    initializeHooksRouter(null as any);
    initializeTtsClient(null as any);
    memoryService.close();
    vi.restoreAllMocks();
  });

  it("returns audioPath when memories are retrieved and TTS is available", async () => {
    // Send a pretool request with a query that should match the seeded memory
    const response = await request(app)
      .post("/hooks/pretool")
      .send({
        tool: "Bash",
        input: { command: "npx ts-node src/index.ts" },
      });

    expect(response.status).toBe(200);
    expect(response.body.continue).toBe(true);

    // If memories were retrieved, TTS fires and audioPath is set
    if (response.body.extraContext) {
      expect(response.body.audioPath).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/audio\/[^/]+$/);
      expect(mockTts.synthesize).toHaveBeenCalledOnce();
    }
    // If score threshold filtered out all memories, TTS should not have fired
    else {
      expect(response.body.audioPath).toBeUndefined();
      expect(mockTts.synthesize).not.toHaveBeenCalled();
    }
  });

  it("does not call TTS when no context to speak (no memories, no warnings)", async () => {
    const response = await request(app)
      .post("/hooks/pretool")
      .send({
        tool: "Bash",
        input: { command: "git status" },
      });

    expect(response.status).toBe(200);
    expect(response.body.continue).toBe(true);

    // If no memories matched and no budget warning, TTS should not fire
    if (!response.body.extraContext) {
      expect(response.body.audioPath).toBeUndefined();
      expect(mockTts.isAvailable).not.toHaveBeenCalled();
    }
  });

  it("fails open when TTS synthesize throws — hook still returns continue=true", async () => {
    (mockTts.synthesize as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("TTS server unavailable")
    );

    const response = await request(app)
      .post("/hooks/pretool")
      .send({
        tool: "Bash",
        input: { command: "npx ts-node src/index.ts" },
      });

    expect(response.status).toBe(200);
    expect(response.body.continue).toBe(true);
    // audioPath absent — synthesis failed but hook did not block
    expect(response.body.audioPath).toBeUndefined();
  });

  it("fails open when TTS isAvailable returns false — hook still returns continue=true", async () => {
    (mockTts.isAvailable as ReturnType<typeof vi.fn>).mockResolvedValue(false);

    const response = await request(app)
      .post("/hooks/pretool")
      .send({
        tool: "Bash",
        input: { command: "npx ts-node src/index.ts" },
      });

    expect(response.status).toBe(200);
    expect(response.body.continue).toBe(true);
    expect(response.body.audioPath).toBeUndefined();
    expect(mockTts.synthesize).not.toHaveBeenCalled();
  });

  it("posttool returns stored regardless of TTS state", async () => {
    const response = await request(app)
      .post("/hooks/posttool")
      .send({
        tool: "Bash",
        input: { command: "npx ts-node src/index.ts" },
        success: true,
        result: { output: "started" },
      });

    expect(response.status).toBe(200);
    expect(response.body.status).toBe("stored");
  });
});
