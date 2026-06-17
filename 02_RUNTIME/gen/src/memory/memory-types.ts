import { MemoryId, ProjectId, UserId, AgentId, MemoryScope, MemoryKind, SensitivityLevel } from "./ids";

export interface MemoryItem {
  id: MemoryId;
  projectId: ProjectId | null;
  ownerUserId: UserId | null;
  authorAgentId: AgentId | null;
  scope: MemoryScope;
  kind: MemoryKind;
  text: string;
  sourceStepId: number | null;
  taskPurpose: string | null;
  sensitivity: SensitivityLevel;
  createdAt: string;
  lastUsedAt: string | null;
  expiresAt: string | null;
  provenanceJson: unknown | null;
}

export interface MemoryACL {
  id: number;
  memoryId: MemoryId;
  subjectType: "agent" | "user" | "project";
  subjectId: string;
  canRead: boolean;
  canWrite: boolean;
}
