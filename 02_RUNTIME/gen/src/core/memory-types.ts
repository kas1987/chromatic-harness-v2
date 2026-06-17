/**
 * Memory data model and ACL types
 */

import {
  MemoryId,
  MemoryScope,
  MemoryKind,
  SensitivityLevel,
  TaskPurpose,
  ProjectId,
  UserId,
} from "./ids";

export interface MemoryItem {
  id: MemoryId;
  projectId: ProjectId;
  ownerUserId: UserId;
  authorAgentId: string;
  scope: MemoryScope;
  kind: MemoryKind;
  text: string;
  sourceStepId?: string;
  taskPurpose?: TaskPurpose;
  sensitivity: SensitivityLevel;
  createdAt: string; // ISO 8601
  lastAccessedAt?: string;
  provenanceJson?: string;
}

export interface MemoryACL {
  id: string;
  memoryId: MemoryId;
  subjectType: "agent_id" | "project_id" | "user_id";
  subjectId: string;
  canRead: boolean;
  canWrite: boolean;
}
