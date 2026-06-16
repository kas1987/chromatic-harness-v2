import fs from "fs";
import path from "path";
import { randomUUID } from "crypto";
import { OllamaClient } from "../ollama/ollama-client.js";
import { submitComfyPrompt } from "../lib/comfy-submit-prompt.js";
import { resolveWorkflowDir } from "../lib/comfy-workflow-path.js";

// ── Types ──────────────────────────────────────────────────────────────────────

export interface ABTestRunConfig {
  basePrompt: string;
  negativePrompt?: string;
  seeds: number[];
  modelPool?: string[];
  ckptName?: string;
  dry_run?: boolean;
}

export type ABTestJobStatus =
  | "pending"
  | "enriching"
  | "queued"
  | "generating"
  | "vision_review"
  | "done"
  | "error";

export interface ABTestJob {
  jobId: string;
  model: string;
  seed: number;
  enrichedPrompt: string;
  comfyPromptId?: string;
  imagePath?: string;
  visionScore?: number;
  visionReasoning?: string;
  status: ABTestJobStatus;
}

export interface ABTestRun {
  runId: string;
  createdAt: string;
  status: "running" | "vision_reviewing" | "done" | "error";
  config: ABTestRunConfig;
  jobs: ABTestJob[];
}

// ── Constants ─────────────────────────────────────────────────────────────────

const VISION_MODEL = "huihui_ai/qwen3-vl-abliterated:4b-instruct";
const ZIMAGE_WORKFLOW = "zimage_txt2img.v1.graph.json";
const DEFAULT_NEGATIVE =
  "bad anatomy, extra limbs, distorted hands, malformed body, deformed fingers, low quality, blurry, watermark, ugly, text, logo";
const ENRICH_TIMEOUT_MS = 12_000;

// ── Workflow helpers (mirrors injectZImage from image-generation.ts) ──────────

function setNodeText(
  wf: Record<string, unknown>,
  nodeId: string,
  text: string,
): void {
  const node = wf[nodeId];
  if (node && typeof node === "object") {
    const inputs = (node as Record<string, unknown>).inputs;
    if (inputs && typeof inputs === "object") {
      (inputs as Record<string, unknown>).text = text;
    }
  }
}

function setNodeCkpt(
  wf: Record<string, unknown>,
  nodeId: string,
  ckpt: string,
): void {
  const node = wf[nodeId];
  if (node && typeof node === "object") {
    const inputs = (node as Record<string, unknown>).inputs;
    if (inputs && typeof inputs === "object") {
      (inputs as Record<string, unknown>).ckpt_name = ckpt;
    }
  }
}

function setNodeSeed(
  wf: Record<string, unknown>,
  nodeId: string,
  seed: number,
): void {
  const node = wf[nodeId];
  if (node && typeof node === "object") {
    const inputs = (node as Record<string, unknown>).inputs;
    if (inputs && typeof inputs === "object") {
      const inp = inputs as Record<string, unknown>;
      inp.seed = seed;
      inp.control_after_generate = "fixed";
    }
  }
}

function buildZImageWorkflow(
  positive: string,
  negative: string,
  seed: number,
  ckptName?: string,
): Record<string, unknown> {
  const workflowPath = path.join(resolveWorkflowDir(), ZIMAGE_WORKFLOW);
  const base = JSON.parse(
    fs.readFileSync(workflowPath, "utf-8"),
  ) as Record<string, unknown>;
  const wf = JSON.parse(JSON.stringify(base)) as Record<string, unknown>;

  // Z-Image node IDs: 2=pos CLIP, 3=neg CLIP, 1=checkpoint, 5=KSampler
  setNodeText(wf, "2", positive);
  setNodeText(wf, "3", negative);
  if (ckptName) setNodeCkpt(wf, "1", ckptName);
  setNodeSeed(wf, "5", Math.floor(seed));

  return wf;
}

// ── ABTestRunner ──────────────────────────────────────────────────────────────

export class ABTestRunner {
  private runs = new Map<string, ABTestRun>();
  // comfyPromptId → job lookup for fast webhook routing
  private comfyJobIndex = new Map<string, ABTestJob>();

  constructor(private readonly client: OllamaClient) {}

  async startRun(config: ABTestRunConfig): Promise<ABTestRun> {
    const runId = randomUUID();
    const models =
      config.modelPool ?? (await this.client.listTextGenModels());
    const negative = config.negativePrompt ?? DEFAULT_NEGATIVE;

    const run: ABTestRun = {
      runId,
      createdAt: new Date().toISOString(),
      status: "running",
      config,
      jobs: [],
    };
    this.runs.set(runId, run);

    for (const model of models) {
      for (const seed of config.seeds) {
        const job: ABTestJob = {
          jobId: randomUUID(),
          model,
          seed,
          enrichedPrompt: "",
          status: "enriching",
        };
        run.jobs.push(job);

        // Enrich prompt with this model (falls back to base on failure)
        job.enrichedPrompt = await this.enrichPrompt(model, config.basePrompt);

        if (config.dry_run) {
          job.status = "done";
          continue;
        }

        // Submit to ComfyUI Z-Image
        try {
          const wf = buildZImageWorkflow(
            job.enrichedPrompt,
            negative,
            seed,
            config.ckptName,
          );
          const comfyPromptId = await submitComfyPrompt(wf, job.jobId);
          job.comfyPromptId = comfyPromptId;
          job.status = "queued";
          this.comfyJobIndex.set(comfyPromptId, job);
        } catch {
          job.status = "error";
        }
      }
    }

    if (config.dry_run) {
      run.status = "done";
    }

    return run;
  }

  async enrichPrompt(model: string, basePrompt: string): Promise<string> {
    const systemPrompt = `You are an expert image generation prompt engineer. Expand the following into a rich, detailed Stable Diffusion positive prompt. Return ONLY the expanded prompt, no explanation.

Prompt: ${basePrompt}`;

    const result = await this.client.generate(model, systemPrompt, {
      temperature: 0.7,
      num_predict: 200,
    });

    return result ?? basePrompt;
  }

  async onComfyComplete(
    comfyPromptId: string,
    imagePath: string,
  ): Promise<void> {
    const job = this.comfyJobIndex.get(comfyPromptId);
    if (!job) return;

    job.imagePath = imagePath;
    job.status = "vision_review";

    // Fire-and-forget vision scoring
    this.scoreWithVision(job).catch(() => {
      job.status = "error";
    });
  }

  private async scoreWithVision(job: ABTestJob): Promise<void> {
    const prompt = `You are a quality evaluator for AI-generated images. Score this image on a scale of 0-10 across three dimensions: anatomy quality, NSFW content execution, and prompt adherence. Image path: ${job.imagePath}. Return your response as: SCORE: <0-10>\nREASON: <one sentence>`;

    const response = await this.client.generate(VISION_MODEL, prompt, {
      temperature: 0.3,
      num_predict: 100,
    });

    if (response) {
      const scoreMatch = response.match(/SCORE:\s*([\d.]+)/i);
      const reasonMatch = response.match(/REASON:\s*(.+)/i);
      job.visionScore = scoreMatch ? parseFloat(scoreMatch[1]) : undefined;
      job.visionReasoning = reasonMatch ? reasonMatch[1].trim() : undefined;
    }

    job.status = "done";
    this.checkRunComplete(job);
  }

  private checkRunComplete(completedJob: ABTestJob): void {
    for (const [, run] of this.runs) {
      if (!run.jobs.includes(completedJob)) continue;
      const allDone = run.jobs.every(
        (j) => j.status === "done" || j.status === "error",
      );
      if (allDone) {
        run.status = "done";
      }
      break;
    }
  }

  getRun(runId: string): ABTestRun | undefined {
    return this.runs.get(runId);
  }

  listRuns(): ABTestRun[] {
    return [...this.runs.values()];
  }
}

// ── Singleton for route/webhook use ──────────────────────────────────────────

let _instance: ABTestRunner | null = null;

export function getABTestRunner(client?: OllamaClient): ABTestRunner {
  if (!_instance) {
    if (!client) throw new Error("ABTestRunner not initialized — pass OllamaClient on first call");
    _instance = new ABTestRunner(client);
  }
  return _instance;
}
