import { MemoryItem, MemoryACL } from "./memory-types";
import { AgentContext } from "./context";
import { canAgentReadMemory } from "./acl-helpers";

export function cosineSimilarity(a: Float32Array, b: Float32Array): number {
  if (a.length !== b.length) return 0;

  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  const denominator = Math.sqrt(normA) * Math.sqrt(normB);
  return denominator === 0 ? 0 : dotProduct / denominator;
}

export interface ScoredMemory {
  memory: MemoryItem;
  score: number;
}

export interface RetrieveOptions {
  maxItems?: number;
  minScore?: number;
}

export function filterAndRankMemories(ctx: AgentContext, scoredCandidates: ScoredMemory[], aclLookup: (memoryId: string) => MemoryACL[], opts: RetrieveOptions = {}): MemoryItem[] {
  const maxItems = opts.maxItems ?? 8;
  const minScore = opts.minScore ?? 0;
  const allowed: ScoredMemory[] = [];

  for (const candidate of scoredCandidates) {
    if (candidate.score < minScore) continue;
    const acls = aclLookup(candidate.memory.id);
    if (!canAgentReadMemory(candidate.memory, acls, ctx)) continue;
    allowed.push(candidate);
  }

  allowed.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return new Date(b.memory.createdAt).getTime() - new Date(a.memory.createdAt).getTime();
  });

  return allowed.slice(0, maxItems).map((x) => x.memory);
}
