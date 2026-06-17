import { describe, it, expect, vi, beforeEach } from "vitest";
import { formatForSpeech } from "../../src/tts/verbal-formatter";
import { OllamaClient } from "../../src/ollama/ollama-client";

vi.mock("../../src/ollama/ollama-client");

describe("formatForSpeech", () => {
  let mockOllamaClient: {
    isAvailable: ReturnType<typeof vi.fn>;
    generate: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockOllamaClient = {
      isAvailable: vi.fn(),
      generate: vi.fn(),
    };
  });

  it("formatForSpeech_withOllama_usesGenerate: returns Ollama output when available", async () => {
    mockOllamaClient.isAvailable.mockResolvedValueOnce(true);
    mockOllamaClient.generate.mockResolvedValueOnce("Your memory has been recalled.");

    const result = await formatForSpeech(
      "• Memory: you prefer TypeScript",
      "mistral:7b",
      mockOllamaClient as unknown as OllamaClient,
    );

    expect(result).toBe("Your memory has been recalled.");
    expect(mockOllamaClient.generate).toHaveBeenCalledOnce();
    const [model, prompt, opts] = mockOllamaClient.generate.mock.calls[0];
    expect(model).toBe("mistral:7b");
    expect(prompt).toContain("Memory: you prefer TypeScript");
    expect(opts).toEqual({ temperature: 0.3 });
  });

  it("formatForSpeech_ollamaUnavailable_fallback: uses simple cleanup when isAvailable=false", async () => {
    mockOllamaClient.isAvailable.mockResolvedValueOnce(false);

    const result = await formatForSpeech(
      "• You prefer TypeScript\n• Always use strict mode",
      "mistral:7b",
      mockOllamaClient as unknown as OllamaClient,
    );

    expect(mockOllamaClient.generate).not.toHaveBeenCalled();
    expect(result).toContain("You prefer TypeScript");
    expect(result).toContain("Always use strict mode");
    expect(result).not.toContain("•");
  });

  it("formatForSpeech_ollamaThrows_fallback: falls back silently when generate throws", async () => {
    mockOllamaClient.isAvailable.mockResolvedValueOnce(true);
    mockOllamaClient.generate.mockRejectedValueOnce(new Error("connection refused"));

    await expect(
      formatForSpeech(
        "• Budget warning: 80% used",
        "mistral:7b",
        mockOllamaClient as unknown as OllamaClient,
      ),
    ).resolves.not.toThrow();

    const result = await formatForSpeech(
      "• Budget warning: 80% used",
      "mistral:7b",
      mockOllamaClient as unknown as OllamaClient,
    );
    expect(result).toContain("Budget warning");
    expect(result).not.toContain("•");
  });

  it("formatForSpeech_bulletStripping: strips bullets and joins newlines with period", async () => {
    const result = await formatForSpeech(
      "• First point\n- Second point\n* Third point",
      "mistral:7b",
      undefined,
    );

    expect(result).not.toMatch(/^[•\-\*]/m);
    expect(result).toContain("First point");
    expect(result).toContain("Second point");
    expect(result).toContain("Third point");
    expect(result).toContain(". ");
  });

  it("formatForSpeech_noOllama_simple: undefined client uses simple cleanup path", async () => {
    const result = await formatForSpeech(
      "• Memory recalled: prefers dark mode\n• Last session: 2026-03-31",
      "mistral:7b",
      undefined,
    );

    expect(result).toContain("Memory recalled");
    expect(result).toContain("Last session");
    expect(result).not.toContain("•");
    expect(result).not.toMatch(/\n/);
  });
});
