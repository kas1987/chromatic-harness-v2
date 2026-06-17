import { describe, it, expect, vi, beforeEach } from "vitest";
import { ABTestRunner } from "../ab-test-runner";
import { OllamaClient } from "../../ollama/ollama-client";

// Mock OllamaClient
vi.mock("../../ollama/ollama-client", () => ({
  OllamaClient: vi.fn().mockImplementation(() => ({
    listTextGenModels: vi.fn().mockResolvedValue(["qwen3:4b", "phi4:latest"]),
    generate: vi.fn().mockResolvedValue("expanded beautiful woman on beach, golden hour, photorealistic"),
    isAvailable: vi.fn().mockResolvedValue(true),
  })),
}));

// Mock submitComfyPrompt
vi.mock("../../lib/comfy-submit-prompt", () => ({
  submitComfyPrompt: vi.fn().mockResolvedValue("comfy-prompt-id-123"),
}));

// Mock fs (workflow loading)
vi.mock("fs", async (importOriginal) => {
  const actual = await importOriginal<typeof import("fs")>();
  return {
    ...actual,
    existsSync: vi.fn().mockReturnValue(true),
    readFileSync: vi.fn().mockReturnValue(
      JSON.stringify({
        "1": { class_type: "CheckpointLoaderSimple", inputs: { ckpt_name: "default.safetensors" } },
        "2": { class_type: "CLIPTextEncode", inputs: { text: "" } },
        "3": { class_type: "CLIPTextEncode", inputs: { text: "" } },
        "5": { class_type: "KSampler", inputs: { seed: 0, control_after_generate: "randomize" } },
      })
    ),
  };
});

describe("ABTestRunner", () => {
  let runner: ABTestRunner;
  let mockClient: OllamaClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mockClient = new OllamaClient();
    runner = new ABTestRunner(mockClient);
  });

  describe("startRun — dry_run mode", () => {
    it("returns enriched prompts for all model×seed combos without ComfyUI submission", async () => {
      const run = await runner.startRun({
        basePrompt: "beautiful woman on beach",
        seeds: [12345, 54321],
        modelPool: ["qwen3:4b", "phi4:latest"],
        dry_run: true,
      });

      // 2 models × 2 seeds = 4 jobs
      expect(run.jobs).toHaveLength(4);
      expect(run.jobs.every((j) => j.status === "done")).toBe(true);
      expect(run.jobs.every((j) => j.comfyPromptId === undefined)).toBe(true);
      expect(run.jobs.every((j) => j.enrichedPrompt.length > 0)).toBe(true);
      expect(run.status).toBe("done");
    });

    it("uses provided modelPool when specified", async () => {
      const run = await runner.startRun({
        basePrompt: "test prompt",
        seeds: [1],
        modelPool: ["qwen3:4b"],
        dry_run: true,
      });

      const models = run.jobs.map((j) => j.model);
      expect(models).toEqual(["qwen3:4b"]);
    });
  });

  describe("enrichPrompt", () => {
    it("falls back to original basePrompt when Ollama returns null", async () => {
      vi.mocked(mockClient.generate).mockResolvedValueOnce(null);

      const result = await runner.enrichPrompt("qwen3:4b", "original prompt");
      expect(result).toBe("original prompt");
    });

    it("returns enriched prompt on successful generation", async () => {
      const enriched = "detailed expanded prompt with lots of tags";
      vi.mocked(mockClient.generate).mockResolvedValueOnce(enriched);

      const result = await runner.enrichPrompt("qwen3:4b", "short prompt");
      expect(result).toBe(enriched);
    });
  });

  describe("onComfyComplete", () => {
    it("updates job status to vision_review when comfyPromptId matches", async () => {
      // Start a non-dry run (but mock submitComfyPrompt)
      const { submitComfyPrompt } = await import("../../lib/comfy-submit-prompt");
      vi.mocked(submitComfyPrompt).mockResolvedValue("known-prompt-id");

      const run = await runner.startRun({
        basePrompt: "test",
        seeds: [1],
        modelPool: ["qwen3:4b"],
        dry_run: false,
      });

      const job = run.jobs[0];
      expect(job.comfyPromptId).toBe("known-prompt-id");
      expect(job.status).toBe("queued");

      // Mock vision scoring to not actually run
      vi.spyOn(runner as any, "scoreWithVision").mockResolvedValue(undefined);

      await runner.onComfyComplete("known-prompt-id", "/outputs/image.png");

      expect(job.imagePath).toBe("/outputs/image.png");
      expect(job.status).toBe("vision_review");
    });

    it("is a no-op when comfyPromptId does not match any job", async () => {
      // No runs started — no jobs to match
      await expect(
        runner.onComfyComplete("unknown-id", "/some/path.png")
      ).resolves.not.toThrow();
    });
  });
});
