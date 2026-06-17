import { nanoid } from "nanoid";
import { MemoryItem, MemoryACL } from "./memory-types";
import { MemoryId, MemoryScope, MemoryKind, SensitivityLevel, memoryId, userId } from "./ids";
import { TaskContext } from "./context";

export interface CreateMemoryInput {
  text: string;
  kind: MemoryKind;
  sourceStepId: number | null;
  sensitivity?: SensitivityLevel;
  scopeOverride?: MemoryScope;
  ownerUserIdOverride?: string | null;
}

export interface CreatedMemoryResult {
  memory: MemoryItem;
  acls: MemoryACL[];
}

export function createMemoryFromStep(ctx: TaskContext, input: CreateMemoryInput): CreatedMemoryResult {
  const now = new Date().toISOString();
  const id: MemoryId = memoryId(nanoid());
  const scope: MemoryScope = input.scopeOverride ?? (input.kind === "preference" ? "user_profile" : ctx.agentRole === "architect" ? "team_scoped" : "agent_private");
  const sensitivity: SensitivityLevel = input.sensitivity ?? "internal";
  const ownerUserId = input.ownerUserIdOverride ? userId(input.ownerUserIdOverride) : ctx.userId ?? null;

  const memory: MemoryItem = {
    id, projectId: scope === "global" ? null : ctx.projectId, ownerUserId, authorAgentId: ctx.agentId,
    scope, kind: input.kind, text: input.text, sourceStepId: input.sourceStepId, taskPurpose: ctx.purpose,
    sensitivity, createdAt: now, lastUsedAt: null, expiresAt: null, provenanceJson: null,
  };

  const acls: MemoryACL[] = [];
  if (scope === "team_scoped" || scope === "global") {
    acls.push({ id: 0, memoryId: memory.id, subjectType: "project", subjectId: ctx.projectId, canRead: true, canWrite: false });
  }
  if (scope === "user_profile" && ownerUserId) {
    acls.push({ id: 0, memoryId: memory.id, subjectType: "user", subjectId: ownerUserId, canRead: true, canWrite: false });
  }
  acls.push({ id: 0, memoryId: memory.id, subjectType: "agent", subjectId: ctx.agentId, canRead: true, canWrite: true });

  return { memory, acls };
}
