import { UserId, ProjectId, AgentId, SessionId, TaskId, TaskPurpose } from "./ids";

export interface AgentContext {
  agentId: AgentId;
  agentRole: string;
  projectId: ProjectId;
  userId?: UserId;
  trustLevel: 0 | 1 | 2;
}

export interface TaskContext extends AgentContext {
  sessionId: SessionId;
  taskId?: TaskId;
  purpose: TaskPurpose;
}
