import { describe, it, expect } from "vitest";
import {
  MemoryScope,
  MemoryKind,
  SensitivityLevel,
  TaskPurpose,
} from "../../src/core/ids";
import type { MemoryItem } from "../../src/core/memory-types";

describe("Memory Types", () => {
  it("MemoryScope enum should have correct values", () => {
    expect(MemoryScope.AGENT_PRIVATE).toBe("agent_private");
    expect(MemoryScope.TEAM_SCOPED).toBe("team_scoped");
    expect(MemoryScope.USER_PROFILE).toBe("user_profile");
    expect(MemoryScope.GLOBAL).toBe("global");
  });

  it("MemoryKind enum should have correct values", () => {
    expect(MemoryKind.SUMMARY).toBe("summary");
    expect(MemoryKind.PREFERENCE).toBe("preference");
    expect(MemoryKind.DECISION).toBe("decision");
    expect(MemoryKind.BUG_FIX).toBe("bug_fix");
  });

  it("MemoryItem interface should satisfy contract", () => {
    const item: MemoryItem = {
      id: "mem-123" as any,
      projectId: "proj-1" as any,
      ownerUserId: "user-1" as any,
      authorAgentId: "agent-1",
      scope: MemoryScope.USER_PROFILE,
      kind: MemoryKind.SUMMARY,
      text: "Test memory",
      sensitivity: SensitivityLevel.INTERNAL,
      createdAt: new Date().toISOString(),
    };

    expect(item.id).toBeDefined();
    expect(item.text).toBe("Test memory");
    expect(item.scope).toBe(MemoryScope.USER_PROFILE);
  });
});
