import { describe, it, expect, vi, beforeEach } from "vitest";
import { OllamaTriage } from "../../src/ollama/ollama-triage";
import { OllamaClient } from "../../src/ollama/ollama-client";

describe("OllamaTriage", () => {
  let client: OllamaClient;
  let triage: OllamaTriage;

  beforeEach(() => {
    client = new OllamaClient();
    triage = new OllamaTriage(client, "mistral:7b", 0.7);
    vi.clearAllMocks();
  });

  it("returns canHandle=true when confidence meets threshold", async () => {
    vi.spyOn(client, "isAvailable").mockResolvedValueOnce(true);
    vi.spyOn(client, "generate").mockResolvedValueOnce(
      "Mistral is a French AI company founded in 2023.\nCONFIDENCE: 0.95",
    );

    const result = await triage.triageExploreTask("What is Mistral AI?");
    expect(result.canHandle).toBe(true);
    expect(result.confidence).toBe(0.95);
    expect(result.result).toContain("Mistral is a French");
    expect(result.result).not.toContain("CONFIDENCE:");
  });

  it("returns canHandle=false when confidence is below threshold", async () => {
    vi.spyOn(client, "isAvailable").mockResolvedValueOnce(true);
    vi.spyOn(client, "generate").mockResolvedValueOnce(
      "I am not sure about the current stock price.\nCONFIDENCE: 0.3",
    );

    const result = await triage.triageExploreTask("What is NVDA stock price right now?");
    expect(result.canHandle).toBe(false);
    expect(result.confidence).toBe(0.3);
  });

  it("returns canHandle=false when Ollama is unavailable", async () => {
    vi.spyOn(client, "isAvailable").mockResolvedValueOnce(false);

    const result = await triage.triageExploreTask("some query");
    expect(result.canHandle).toBe(false);
    expect(result.confidence).toBe(0);
  });

  it("returns canHandle=false when generate returns null", async () => {
    vi.spyOn(client, "isAvailable").mockResolvedValueOnce(true);
    vi.spyOn(client, "generate").mockResolvedValueOnce(null);

    const result = await triage.triageExploreTask("some query");
    expect(result.canHandle).toBe(false);
    expect(result.confidence).toBe(0);
  });

  it("strips CONFIDENCE line from result text", async () => {
    vi.spyOn(client, "isAvailable").mockResolvedValueOnce(true);
    vi.spyOn(client, "generate").mockResolvedValueOnce(
      "The answer is 42.\nCONFIDENCE: 0.8",
    );

    const result = await triage.triageExploreTask("what is the answer");
    expect(result.result).toBe("The answer is 42.");
    expect(result.result).not.toContain("CONFIDENCE");
  });

  it("handles CONFIDENCE: 0.0 (exactly at zero)", async () => {
    vi.spyOn(client, "isAvailable").mockResolvedValueOnce(true);
    vi.spyOn(client, "generate").mockResolvedValueOnce(
      "No idea.\nCONFIDENCE: 0.0",
    );

    const result = await triage.triageExploreTask("predict tomorrow's lottery numbers");
    expect(result.canHandle).toBe(false);
    expect(result.confidence).toBe(0.0);
  });

  it("respects custom confidenceThreshold", async () => {
    const strictTriage = new OllamaTriage(client, "mistral:7b", 0.9);
    vi.spyOn(client, "isAvailable").mockResolvedValueOnce(true);
    vi.spyOn(client, "generate").mockResolvedValueOnce("Answer.\nCONFIDENCE: 0.85");

    const result = await strictTriage.triageExploreTask("query");
    expect(result.canHandle).toBe(false); // 0.85 < 0.9 threshold
  });

  it("includes model name in result", async () => {
    vi.spyOn(client, "isAvailable").mockResolvedValueOnce(false);
    const result = await triage.triageExploreTask("query");
    expect(result.model).toBe("mistral:7b");
  });
});
