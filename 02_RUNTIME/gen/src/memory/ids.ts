export type UserId = string & { readonly __brand: "UserId" };
export type ProjectId = string & { readonly __brand: "ProjectId" };
export type AgentId = string & { readonly __brand: "AgentId" };
export type SessionId = string & { readonly __brand: "SessionId" };
export type TaskId = string & { readonly __brand: "TaskId" };
export type MemoryId = string & { readonly __brand: "MemoryId" };

export const userId = (id: string): UserId => id as UserId;
export const projectId = (id: string): ProjectId => id as ProjectId;
export const agentId = (id: string): AgentId => id as AgentId;
export const sessionId = (id: string): SessionId => id as SessionId;
export const taskId = (id: string): TaskId => id as TaskId;
export const memoryId = (id: string): MemoryId => id as MemoryId;

export type MemoryScope = "agent_private" | "team_scoped" | "user_profile" | "global";
export type MemoryKind = "fact" | "summary" | "preference" | "outcome";
export type SensitivityLevel = "public" | "internal" | "confidential";
export type SubjectType = "agent" | "user" | "project";
export type TaskPurpose = "bugfix" | "refactor" | "feature" | "investigation" | "maintenance" | "other";
