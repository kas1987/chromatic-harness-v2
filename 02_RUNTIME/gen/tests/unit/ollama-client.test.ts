import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { OllamaClient } from "../../src/ollama/ollama-client";

// Mock node-fetch at module level
vi.mock("node-fetch", () => ({
  default: vi.fn(),
}));

import fetch from "node-fetch";
const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;

describe("OllamaClient", () => {
  let client: OllamaClient;

  beforeEach(() => {
    client = new OllamaClient("http://127.0.0.1:11434", 5_000);
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("isAvailable", () => {
    it("returns true when /api/tags responds ok", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });
      const result = await client.isAvailable();
      expect(result).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        "http://127.0.0.1:11434/api/tags",
        expect.objectContaining({ signal: expect.anything() }),
      );
    });

    it("returns false when /api/tags responds not ok", async () => {
      mockFetch.mockResolvedValueOnce({ ok: false });
      expect(await client.isAvailable()).toBe(false);
    });

    it("returns false when fetch throws (server down)", async () => {
      mockFetch.mockRejectedValueOnce(new Error("ECONNREFUSED"));
      expect(await client.isAvailable()).toBe(false);
    });
  });

  describe("listModels", () => {
    it("returns model names from /api/tags response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          models: [{ name: "mistral:7b" }, { name: "llava:13b" }],
        }),
      });
      const models = await client.listModels();
      expect(models).toEqual(["mistral:7b", "llava:13b"]);
    });

    it("returns empty array on non-ok response", async () => {
      mockFetch.mockResolvedValueOnce({ ok: false });
      expect(await client.listModels()).toEqual([]);
    });

    it("returns empty array on fetch error", async () => {
      mockFetch.mockRejectedValueOnce(new Error("network error"));
      expect(await client.listModels()).toEqual([]);
    });

    it("handles missing models field gracefully", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });
      expect(await client.listModels()).toEqual([]);
    });
  });

  describe("generate", () => {
    it("returns response text on success", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ model: "mistral:7b", response: "hello world", done: true }),
      });
      const result = await client.generate("mistral:7b", "say hello");
      expect(result).toBe("hello world");
    });

    it("sends correct payload to /api/generate", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ model: "mistral:7b", response: "ok", done: true }),
      });
      await client.generate("mistral:7b", "test prompt", { temperature: 0.5 });
      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      expect(body.model).toBe("mistral:7b");
      expect(body.prompt).toBe("test prompt");
      expect(body.stream).toBe(false);
      expect(body.options.temperature).toBe(0.5);
    });

    it("returns null on non-ok response", async () => {
      mockFetch.mockResolvedValueOnce({ ok: false });
      expect(await client.generate("mistral:7b", "test")).toBeNull();
    });

    it("returns null on fetch error", async () => {
      mockFetch.mockRejectedValueOnce(new Error("timeout"));
      expect(await client.generate("mistral:7b", "test")).toBeNull();
    });
  });

  describe("generateJSON", () => {
    it("parses JSON object embedded in response text", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          model: "mistral:7b",
          response: 'Sure! Here is the answer: {"intent":"read_file","category":"exploration","risk_level":"low","summary":"Read a config file"}',
          done: true,
        }),
      });
      const result = await client.generateJSON<{ intent: string }>("mistral:7b", "classify");
      expect(result?.intent).toBe("read_file");
    });

    it("returns null when response contains no JSON", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ model: "mistral:7b", response: "No JSON here at all", done: true }),
      });
      expect(await client.generateJSON("mistral:7b", "classify")).toBeNull();
    });

    it("returns null when generate returns null", async () => {
      mockFetch.mockRejectedValueOnce(new Error("down"));
      expect(await client.generateJSON("mistral:7b", "classify")).toBeNull();
    });

    it("returns null when extracted JSON is malformed", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ model: "mistral:7b", response: "{ bad json }", done: true }),
      });
      expect(await client.generateJSON("mistral:7b", "classify")).toBeNull();
    });
  });
});
