import { describe, it, expect, vi, beforeEach } from "vitest";
import { OllamaClient } from "../ollama-client";

describe("OllamaClient.listTextGenModels", () => {
  let client: OllamaClient;

  beforeEach(() => {
    client = new OllamaClient();
  });

  it("filters out embed, tagger, coder, vl, llava, nomic models", async () => {
    vi.spyOn(client, "listModels").mockResolvedValue([
      "qwen3:4b",
      "gemma4:e4b-it-q4_K_M",
      "nomic-embed-text:latest",
      "nsfw-tagger:latest",
      "qwen2.5-coder:14b",
      "huihui_ai/qwen3-vl-abliterated:4b-instruct",
      "llava:7b",
      "phi4:latest",
      "mistral:latest",
      "deepseek-r1:8b",
    ]);

    const result = await client.listTextGenModels();

    expect(result).toContain("qwen3:4b");
    expect(result).toContain("gemma4:e4b-it-q4_K_M");
    expect(result).toContain("phi4:latest");
    expect(result).toContain("mistral:latest");
    expect(result).toContain("deepseek-r1:8b");

    expect(result).not.toContain("nomic-embed-text:latest");
    expect(result).not.toContain("nsfw-tagger:latest");
    expect(result).not.toContain("qwen2.5-coder:14b");
    expect(result).not.toContain("huihui_ai/qwen3-vl-abliterated:4b-instruct");
    expect(result).not.toContain("llava:7b");
  });

  it("returns empty array when listModels returns empty", async () => {
    vi.spyOn(client, "listModels").mockResolvedValue([]);
    const result = await client.listTextGenModels();
    expect(result).toEqual([]);
  });

  it("returns all models when none match the exclude list", async () => {
    vi.spyOn(client, "listModels").mockResolvedValue([
      "phi4:latest",
      "mistral:latest",
    ]);
    const result = await client.listTextGenModels();
    expect(result).toHaveLength(2);
  });
});
