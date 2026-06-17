import { describe, it, expect } from "vitest";
import {
  dedupeAdjacentSteps,
  filterRoutingStepsForVram,
  getRoutingSteps,
} from "../../src/routing/routing-matrix.js";

describe("routing-matrix", () => {
  it("getRoutingSteps: classify-route returns gemma then ollama then claude", () => {
    const steps = getRoutingSteps("classify-route");
    expect(steps).not.toBeNull();
    expect(steps!.map((s) => s.provider)).toEqual(["gemma", "ollama", "claude"]);
    expect(steps![0].localModelTag).toBe("gemma3:4b");
    expect(steps![1].localModelTag).toBe("qwen3:4b");
    expect(steps![2].localModelTag).toBeUndefined();
  });

  it("getRoutingSteps: unknown intent returns null", () => {
    expect(getRoutingSteps("not-a-real-intent")).toBeNull();
  });

  it("getRoutingSteps: blank intent returns null", () => {
    expect(getRoutingSteps("")).toBeNull();
    expect(getRoutingSteps("   ")).toBeNull();
    expect(getRoutingSteps(undefined)).toBeNull();
  });

  it("dedupeAdjacentSteps: collapses consecutive identical steps", () => {
    const steps = dedupeAdjacentSteps([
      { provider: "ollama", localModelTag: "a:1" },
      { provider: "ollama", localModelTag: "a:1" },
      { provider: "claude" },
    ]);
    expect(steps).toHaveLength(2);
    expect(steps[0].provider).toBe("ollama");
    expect(steps[1].provider).toBe("claude");
  });

  it("filterRoutingStepsForVram: removes ollama and gemma when unsafe", () => {
    const steps = [
      { provider: "gemma" as const, localModelTag: "x" },
      { provider: "ollama" as const, localModelTag: "y" },
      { provider: "claude" as const },
    ];
    expect(filterRoutingStepsForVram(steps, false)).toEqual([{ provider: "claude" }]);
    expect(filterRoutingStepsForVram(steps, true)).toEqual(steps);
  });
});
