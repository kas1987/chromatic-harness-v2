/**
 * Context objects for agent and task execution
 */

import { AgentId, ProjectId, UserId, TaskId, TaskPurpose } from "./ids";

export interface AgentContext {
  agentId: AgentId;
  agentRole: string; // "coder", "architect", "qa", "intern", "system"
  projectId: ProjectId;
  userId: UserId;
  trustLevel: 0 | 1 | 2; // 0=intern, 1=coder/qa, 2=architect/system
}

export interface TaskContext extends AgentContext {
  sessionId: string;
  taskId: TaskId;
  purpose: TaskPurpose;
}
