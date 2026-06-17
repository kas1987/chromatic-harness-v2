/**
 * Branded type aliases for type-safe identifiers
 */

export type UserId = string & { readonly __brand: "UserId" };
export type ProjectId = string & { readonly __brand: "ProjectId" };
export type AgentId = string & { readonly __brand: "AgentId" };
export type TaskId = string & { readonly __brand: "TaskId" };
export type MemoryId = string & { readonly __brand: "MemoryId" };

export enum MemoryScope {
  AGENT_PRIVATE = "agent_private",
  TEAM_SCOPED = "team_scoped",
  USER_PROFILE = "user_profile",
  GLOBAL = "global",
}

export enum MemoryKind {
  SUMMARY = "summary",
  PREFERENCE = "preference",
  DECISION = "decision",
  BUG_FIX = "bug_fix",
}

export enum SensitivityLevel {
  PUBLIC = "public",
  INTERNAL = "internal",
  CONFIDENTIAL = "confidential",
}

export enum TaskPurpose {
  CODE = "code",
  DEBUG = "debug",
  TEST = "test",
  DEPLOY = "deploy",
  OTHER = "other",
}
