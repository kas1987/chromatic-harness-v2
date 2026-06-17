import { describe, it, expect } from "vitest";
import { selectVoice, type VoiceContext } from "../../src/tts/voice-router";

describe("selectVoice", () => {
  it("budget_stop maps to Eve (warning_urgent role)", () => {
    expect(selectVoice("budget_stop")).toBe("Eve");
  });

  it("memory_recall maps to Relaxing_Rachel (memory_injection role)", () => {
    expect(selectVoice("memory_recall")).toBe("Relaxing_Rachel");
  });

  it("default maps to UA___20s_Woman (assistant_default role)", () => {
    expect(selectVoice("default")).toBe("UA___20s_Woman");
  });

  it("unknown context falls back to UA___20s_Woman", () => {
    expect(selectVoice("unknown_context" as VoiceContext)).toBe("UA___20s_Woman");
  });
});
