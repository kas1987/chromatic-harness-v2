import { describe, it, expect } from "vitest";
import { classifyTaskComplexity } from "../../src/budget/task-complexity-classifier.js";

describe("classifyTaskComplexity", () => {
  it("'run ls /tmp' → simple (bash single command)", () => {
    expect(classifyTaskComplexity({ description: "run ls /tmp" })).toBe("simple");
  });

  it("'run council validation with spawning' → complex", () => {
    expect(classifyTaskComplexity({ description: "run council validation with spawning" })).toBe("complex");
  });

  it("'run discovery phase' → complex", () => {
    expect(classifyTaskComplexity({ description: "run discovery phase" })).toBe("complex");
  });

  it("'read gen/src/budget/budget-config.ts' → simple", () => {
    expect(classifyTaskComplexity({ description: "read gen/src/budget/budget-config.ts" })).toBe("simple");
  });

  it("Read tool → simple regardless of description", () => {
    expect(classifyTaskComplexity({ toolName: "Read", description: "run council validation" })).toBe("simple");
  });

  it("Glob tool → simple", () => {
    expect(classifyTaskComplexity({ toolName: "Glob" })).toBe("simple");
  });

  it("command over 500 chars → complex", () => {
    expect(classifyTaskComplexity({ commandLength: 600 })).toBe("complex");
  });

  it("command under 500 chars → simple", () => {
    expect(classifyTaskComplexity({ commandLength: 100 })).toBe("simple");
  });
});
