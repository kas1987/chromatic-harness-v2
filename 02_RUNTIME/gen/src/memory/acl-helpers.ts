import { MemoryItem, MemoryACL } from "./memory-types";
import { AgentContext } from "./context";

export function canAgentReadMemory(memory: MemoryItem, acls: MemoryACL[], ctx: AgentContext): boolean {
  if (memory.scope !== "global") {
    if (!memory.projectId || memory.projectId !== ctx.projectId) return false;
  }
  if (memory.sensitivity === "confidential" && ctx.trustLevel < 2) return false;

  let hasReadPermission = false;
  for (const acl of acls) {
    if (!acl.canRead) continue;
    if ((acl.subjectType === "agent" && acl.subjectId === ctx.agentId) ||
        (acl.subjectType === "user" && ctx.userId && acl.subjectId === ctx.userId) ||
        (acl.subjectType === "project" && acl.subjectId === ctx.projectId)) {
      hasReadPermission = true;
      break;
    }
  }
  if (!hasReadPermission) return false;

  switch (memory.scope) {
    case "agent_private": return memory.authorAgentId === ctx.agentId;
    case "user_profile": return memory.ownerUserId != null && ctx.userId === memory.ownerUserId;
    case "team_scoped":
    case "global": return true;
    default: return false;
  }
}
