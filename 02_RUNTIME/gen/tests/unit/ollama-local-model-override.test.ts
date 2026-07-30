import { describe, it, expect, vi, beforeEach } from "vitest";

const ollamaGenerate = vi.hoisted(() => vi.fn().mockResolvedValue("mocked-out"));

vi.mock("../../src/ollama/ollama-client.js", () => ({
  OllamaClient: vi.fn(function () {
    return {
      generate: ollamaGenerate,
      isAvailable: vi.fn().mockResolvedValue(true),
      listModels: vi.fn().mockResolvedValue(["gemma3:4b", "qwen3:4b"]),
    };
  }),
}));

import { OllamaClientWrapper, GemmaOllamaClient } from "../../src/llm/llm-client-factory.js";

describe("localModelTag on Ollama-backed ILlmClient", () => {
  beforeEach(() => {
    ollamaGenerate.mockClear();
  });

  it("OllamaClientWrapper passes localModelTag to OllamaClient.generate", async () => {
    const gen = ollamaGenerate;
    const cfg = {
      ollamaUrl: "http://127.0.0.1:11434",
      ollamaModel: "default-model:tag",
      gemmaOllamaModel: "gemma3:4b",
      enableGemma: true,
    } as any;

    const w = new OllamaClientWrapper(cfg);
    await w.generate("hello", { localModelTag: "override:7b" });
    expect(gen).toHaveBeenCalledWith(
      "override:7b",
      "hello",
      expect.objectContaining({ temperature: 0.7 }),
    );
  });

  it("OllamaClientWrapper uses config default when localModelTag omitted", async () => {
    const gen = ollamaGenerate;
    const cfg = {
      ollamaUrl: "http://127.0.0.1:11434",
      ollamaModel: "qwen3:4b",
      gemmaOllamaModel: "gemma3:4b",
      enableGemma: true,
    } as any;

    const w = new OllamaClientWrapper(cfg);
    await w.generate("hello");
    expect(gen).toHaveBeenCalledWith(
      "qwen3:4b",
      "hello",
      expect.objectContaining({ temperature: 0.7 }),
    );
  });

  it("GemmaOllamaClient passes localModelTag to OllamaClient.generate", async () => {
    const gen = ollamaGenerate;
    const cfg = {
      ollamaUrl: "http://127.0.0.1:11434",
      ollamaModel: "qwen3:4b",
      gemmaOllamaModel: "gemma3:4b",
      enableGemma: true,
    } as any;

    const w = new GemmaOllamaClient(cfg);
    await w.generate("hi", { localModelTag: "custom-gemma:tag" });
    expect(gen).toHaveBeenCalledWith(
      "custom-gemma:tag",
      "hi",
      expect.objectContaining({ temperature: 0.7 }),
    );
  });
});
