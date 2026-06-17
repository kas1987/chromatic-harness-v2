import { MemoryStore } from "./memory-store";
import { EmbeddingProvider } from "./embedding-provider";
import { TaskContext, AgentContext } from "./context";
import { MemoryItem } from "./memory-types";
import { cosineSimilarity } from "./memory-retrieve";
import type { IEmbeddingProvider } from "./embedding-provider";
import { getTracer } from "../otel/tracer";
import { GEN_ATTRS } from "../otel/attributes";

export class MemoryService {
  private store: MemoryStore;
  private embeddings: IEmbeddingProvider | null;

  constructor(store: MemoryStore, embeddings?: IEmbeddingProvider) {
    this.store = store;
    this.embeddings = embeddings ?? null;
  }

  public async createMemory(ctx: TaskContext, input: {
    text: string; kind: string; sourceStepId?: number | null; sensitivity?: string;
    scopeOverride?: string; ownerUserIdOverride?: string | null;
  }): Promise<MemoryItem> {
    let embedding: Float32Array | null = null;
    if (this.embeddings) {
      try {
        embedding = await this.embeddings.embed(input.text);
      } catch (err) {
        console.warn("Embedding failed, continuing:", err);
      }
    }
    return this.store.createAndStoreMemoryFromStep(ctx, {
      text: input.text, kind: input.kind, sourceStepId: input.sourceStepId ?? null,
      sensitivity: input.sensitivity, scopeOverride: input.scopeOverride,
      ownerUserIdOverride: input.ownerUserIdOverride, embedding,
    });
  }

  public async retrieveMemories(ctx: AgentContext, query: string, options?: { maxItems?: number; minScore?: number }): Promise<MemoryItem[]> {
    const span = getTracer().startSpan("memory.retrieve", {
      attributes: {
        [GEN_ATTRS.AGENT_ROLE]: ctx.agentRole,
        [GEN_ATTRS.PROJECT_ID]: ctx.projectId as string,
      },
    });

    try {
      const candidates = this.store.getRecentCandidatesForProject(ctx.projectId, null, 50);

      let result: MemoryItem[];

      if (!this.embeddings) {
        result = this.store.filterAndRankForAgent(ctx, candidates.map((c) => ({ memory: c, score: 1 })), options);
        span.setAttribute(GEN_ATTRS.EMBEDDING_CACHE_HIT, false);
      } else {
        let queryEmbedding: Float32Array;
        try {
          queryEmbedding = await this.embeddings.embed(query);
        } catch (err) {
          result = this.store.filterAndRankForAgent(ctx, candidates.map((c) => ({ memory: c, score: 1 })), options);
          span.setAttribute(GEN_ATTRS.EMBEDDING_CACHE_HIT, false);
          span.setAttribute(GEN_ATTRS.MEMORIES_RETURNED, result.length);
          span.end();
          return result;
        }

        const scoredCandidates = candidates.map((memory) => {
          const memEmbedding = this.store.getEmbedding(memory.id);
          const score = memEmbedding ? cosineSimilarity(queryEmbedding, memEmbedding) : 0;
          return { memory, score };
        }).filter((x) => x.score > 0);

        result = this.store.filterAndRankForAgent(ctx, scoredCandidates, options);
        span.setAttribute(GEN_ATTRS.EMBEDDING_CACHE_HIT, true);
      }

      span.setAttribute(GEN_ATTRS.MEMORIES_RETURNED, result.length);
      span.end();
      return result;
    } catch (err) {
      span.recordException(err as Error);
      span.end();
      throw err;
    }
  }

  public close(): void {
    this.store.close();
  }
}
