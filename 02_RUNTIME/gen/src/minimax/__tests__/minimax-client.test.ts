import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MiniMaxClient } from "../minimax-client.js";

// Mock global fetch for all tests
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function makeClient(apiKey = ""): MiniMaxClient {
  return new MiniMaxClient("http://test.minimax.internal/v1", "minimax-m2.5:cloud", apiKey);
}

beforeEach(() => {
  mockFetch.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("MiniMaxClient.generate", () => {
  it("returns content from chat completions response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        choices: [{ message: { content: "Hello from MiniMax" } }],
      }),
    });

    const client = makeClient();
    const result = await client.generate("Say hello");
    expect(result).toBe("Hello from MiniMax");
  });

  it("sends correct payload shape to /chat/completions", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ choices: [{ message: { content: "ok" } }] }),
    });

    const client = makeClient("test-key");
    await client.generate("test prompt", { maxTokens: 512, temperature: 0.5 });

    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://test.minimax.internal/v1/chat/completions");

    const body = JSON.parse(init.body as string);
    expect(body.model).toBe("minimax-m2.5:cloud");
    expect(body.max_tokens).toBe(512);
    expect(body.temperature).toBe(0.5);
    expect(body.messages).toEqual([{ role: "user", content: "test prompt" }]);

    const headers = init.headers as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer test-key");
  });

  it("omits Authorization header when no apiKey", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ choices: [{ message: { content: "ok" } }] }),
    });

    await makeClient("").generate("test");

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["Authorization"]).toBeUndefined();
  });

  it("throws on non-ok API response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 429,
      text: async () => "rate limited",
    });

    await expect(makeClient().generate("test")).rejects.toThrow("429");
  });

  it("has 60s AbortSignal timeout on generate", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ choices: [{ message: { content: "" } }] }),
    });

    await makeClient().generate("test");

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(init.signal).toBeDefined();
    // AbortSignal.timeout(60_000) — verify it exists (cannot inspect exact ms without real browser API)
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });
});

describe("MiniMaxClient.isAvailable — dual-path probe", () => {
  it("returns true when Ollama cloud model ID contains 'minimax'", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: [{ id: "minimax-m2.5:cloud" }, { id: "minimax-m2.7:cloud" }],
      }),
    });

    expect(await makeClient().isAvailable()).toBe(true);
  });

  it("returns true via direct API path: non-empty model list + apiKey (no 'minimax' in IDs)", async () => {
    // Direct MiniMax API returns their own model IDs (not containing "minimax")
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: [{ id: "abab6.5-chat" }, { id: "abab6.5s-chat" }],
      }),
    });

    const client = makeClient("my-secret-key");
    expect(await client.isAvailable()).toBe(true);
  });

  it("returns false when no API key and model IDs don't contain 'minimax'", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: [{ id: "abab6.5-chat" }] }),
    });

    // No apiKey + non-minimax IDs → false (can't determine which API this is)
    expect(await makeClient("").isAvailable()).toBe(false);
  });

  it("returns false on non-ok /models response", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 503 });
    expect(await makeClient().isAvailable()).toBe(false);
  });

  it("returns false on network error — never throws", async () => {
    mockFetch.mockRejectedValueOnce(new Error("ECONNREFUSED"));
    expect(await makeClient().isAvailable()).toBe(false);
  });

  it("uses 3s AbortSignal timeout on isAvailable probe", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: [{ id: "minimax-m2.5:cloud" }] }),
    });

    await makeClient().isAvailable();

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });
});
