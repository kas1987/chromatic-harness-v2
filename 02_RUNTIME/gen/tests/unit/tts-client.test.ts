import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import path from "path";
import { TtsClient, TtsSynthesisError } from "../../src/tts/tts-client";

// Mock node-fetch at module level
vi.mock("node-fetch", () => ({
  default: vi.fn(),
}));

// Mock fs.promises
vi.mock("fs", () => ({
  default: {
    promises: {
      writeFile: vi.fn().mockResolvedValue(undefined),
      readdir: vi.fn().mockResolvedValue([]),
      stat: vi.fn(),
      unlink: vi.fn().mockResolvedValue(undefined),
    },
  },
  promises: {
    writeFile: vi.fn().mockResolvedValue(undefined),
    readdir: vi.fn().mockResolvedValue([]),
    stat: vi.fn(),
    unlink: vi.fn().mockResolvedValue(undefined),
  },
}));

import fetch from "node-fetch";
const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;

describe("TtsClient", () => {
  let client: TtsClient;
  const audioDir = "/tmp/tts-audio";

  beforeEach(() => {
    client = new TtsClient("http://127.0.0.1:8765", audioDir, 5_000);
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("isAvailable", () => {
    it("returns true when /v1/health responds ok", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });
      const result = await client.isAvailable();
      expect(result).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8765/v1/health",
        expect.objectContaining({ signal: expect.anything() }),
      );
    });

    it("returns false when fetch throws (server down)", async () => {
      mockFetch.mockRejectedValueOnce(new Error("ECONNREFUSED"));
      expect(await client.isAvailable()).toBe(false);
    });
  });

  describe("listVoices", () => {
    it("unwraps { voices: string[] } response object", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ voices: ["UA___20s_Woman", "Eve", "Relaxing_Rachel"] }),
      });
      const voices = await client.listVoices();
      expect(voices).toEqual(["UA___20s_Woman", "Eve", "Relaxing_Rachel"]);
    });

    it("returns empty array when voices key missing", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });
      expect(await client.listVoices()).toEqual([]);
    });
  });

  describe("synthesize", () => {
    it("saves WAV bytes and returns audioPath", async () => {
      const wavBytes = new ArrayBuffer(44); // minimal WAV header size
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: { get: (h: string) => h === "content-type" ? "audio/wav" : null },
        arrayBuffer: async () => wavBytes,
      });

      const result = await client.synthesize("hello world", "UA___20s_Woman");

      expect(result.voiceId).toBe("UA___20s_Woman");
      expect(result.audioPath).toMatch(/\.wav$/);
      // Verify the filename is in the expected directory by checking dirname
      const { default: pathMod } = await import("path");
      expect(pathMod.dirname(result.audioPath)).toBe(pathMod.join(audioDir));
      expect(result.durationMs).toBeGreaterThanOrEqual(0);
    });

    it("throws TtsSynthesisError when res.ok is false", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: "voice not found" }),
      });

      await expect(
        client.synthesize("hello", "invalid_voice"),
      ).rejects.toThrow(TtsSynthesisError);

      await expect(
        client.synthesize("hello", "invalid_voice"),
      ).rejects.toThrow("422");
    });

    it("throws TtsSynthesisError on fetch timeout/abort", async () => {
      mockFetch.mockRejectedValueOnce(
        Object.assign(new Error("The operation was aborted"), { name: "AbortError" }),
      );

      await expect(
        client.synthesize("hello", "UA___20s_Woman"),
      ).rejects.toThrow(TtsSynthesisError);
    });

    it("includes language param in request body", async () => {
      const wavBytes = new ArrayBuffer(44);
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: { get: (h: string) => h === "content-type" ? "audio/wav" : null },
        arrayBuffer: async () => wavBytes,
      });

      await client.synthesize("hello", "UA___20s_Woman", "English");

      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body as string);
      expect(body.language).toBe("English");
      expect(body.voice_id).toBe("UA___20s_Woman");
      expect(body.text).toBe("hello");
    });
  });
});
