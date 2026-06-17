import { describe, it, expect, vi, beforeEach } from "vitest";
import { OllamaEnricher } from "../../src/ollama/ollama-enricher";
import { OllamaClient } from "../../src/ollama/ollama-client";

describe("OllamaEnricher", () => {
  let client: OllamaClient;
  let enricher: OllamaEnricher;

  beforeEach(() => {
    client = new OllamaClient();
    enricher = new OllamaEnricher(client, "mistral:7b");
    vi.clearAllMocks();
  });

  it("returns enrichment tags on success", async () => {
    const tags = {
      intent: "write_file",
      category: "code_change",
      risk_level: "low" as const,
      summary: "Wrote TypeScript source file",
    };
    vi.spyOn(client, "generateJSON").mockResolvedValueOnce(tags);

    const result = await enricher.enrichEvent("Write", { file_path: "src/foo.ts" }, true);
    expect(result).toEqual(tags);
  });

  it("returns null when Ollama is unavailable", async () => {
    vi.spyOn(client, "generateJSON").mockResolvedValueOnce(null);
    const result = await enricher.enrichEvent("Edit", { file_path: "src/bar.ts" }, true);
    expect(result).toBeNull();
  });

  it("builds correct prompt for Bash tool", async () => {
    const spy = vi.spyOn(client, "generateJSON").mockResolvedValueOnce(null);
    await enricher.enrichEvent("Bash", { command: "npm test" }, true);

    const prompt = spy.mock.calls[0][1] as string;
    expect(prompt).toContain("Tool: Bash");
    expect(prompt).toContain("npm test");
  });

  it("builds correct prompt for Write tool", async () => {
    const spy = vi.spyOn(client, "generateJSON").mockResolvedValueOnce(null);
    await enricher.enrichEvent("Write", { file_path: "src/config.ts" }, false);

    const prompt = spy.mock.calls[0][1] as string;
    expect(prompt).toContain("Tool: Write");
    expect(prompt).toContain("src/config.ts");
    expect(prompt).toContain("Succeeded: false");
  });

  it("builds correct prompt for WebFetch tool", async () => {
    const spy = vi.spyOn(client, "generateJSON").mockResolvedValueOnce(null);
    await enricher.enrichEvent("WebFetch", { url: "https://example.com" }, true);

    const prompt = spy.mock.calls[0][1] as string;
    expect(prompt).toContain("https://example.com");
  });

  it("uses low temperature for consistent classification", async () => {
    const spy = vi.spyOn(client, "generateJSON").mockResolvedValueOnce(null);
    await enricher.enrichEvent("Bash", { command: "ls" }, true);

    const options = spy.mock.calls[0][2] as { temperature?: number };
    expect(options?.temperature).toBeLessThanOrEqual(0.1);
  });

  it("does not throw when generateJSON rejects", async () => {
    vi.spyOn(client, "generateJSON").mockRejectedValueOnce(new Error("oops"));
    await expect(enricher.enrichEvent("Read", { file_path: "x.ts" }, true)).resolves.toBeNull();
  });
});
