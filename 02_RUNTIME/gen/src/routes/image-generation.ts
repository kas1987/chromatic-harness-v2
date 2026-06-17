import { Router, Request, Response } from 'express';
import fs from 'fs';
import path from 'path';
import type { GenerationQueueService } from '../services/generation-queue-service';
import { resolveWorkflowDir } from '../lib/comfy-workflow-path';
import { submitComfyPrompt } from '../lib/comfy-submit-prompt';

export const imageGenerationRouter = Router();

let queueService: GenerationQueueService | null = null;

const DEFAULT_NEG_ZIMAGE =
  'bad anatomy, extra limbs, distorted hands, malformed body, deformed fingers, low quality, blurry, watermark, ugly, text, logo';
const DEFAULT_NEG_SDXL =
  'worst quality, low quality, bad anatomy, extra limbs, distorted hands, malformed body, deformed fingers, blurry, watermark, ugly, mutation, disfigured';

export function initializeImageGenerationRouter(queue: GenerationQueueService | null): void {
  queueService = queue;
}

function loadWorkflowFile(name: string): Record<string, unknown> {
  const workflowPath = path.join(resolveWorkflowDir(), name);
  if (!fs.existsSync(workflowPath)) {
    throw new Error(`Workflow not found: ${workflowPath}`);
  }
  return JSON.parse(fs.readFileSync(workflowPath, 'utf-8'));
}

function setClipText(
  wf: Record<string, unknown>,
  nodeId: string,
  text: string,
): void {
  const node = wf[nodeId];
  if (node && typeof node === 'object') {
    const inputs = (node as Record<string, unknown>).inputs;
    if (inputs && typeof inputs === 'object') {
      (inputs as Record<string, unknown>).text = text;
    }
  }
}

function setCkptName(wf: Record<string, unknown>, nodeId: string, ckpt: string): void {
  const node = wf[nodeId];
  if (node && typeof node === 'object') {
    const inputs = (node as Record<string, unknown>).inputs;
    if (inputs && typeof inputs === 'object') {
      (inputs as Record<string, unknown>).ckpt_name = ckpt;
    }
  }
}

function setKsamplerSeed(wf: Record<string, unknown>, nodeId: string, seed: number): void {
  const node = wf[nodeId];
  if (node && typeof node === 'object') {
    const inputs = (node as Record<string, unknown>).inputs;
    if (inputs && typeof inputs === 'object') {
      const inp = inputs as Record<string, unknown>;
      inp.seed = seed;
      inp.control_after_generate = 'fixed';
    }
  }
}

function injectZImage(
  base: Record<string, unknown>,
  positive: string,
  negative: string,
  opts: { ckpt_name?: string; seed?: number },
): Record<string, unknown> {
  const wf = JSON.parse(JSON.stringify(base)) as Record<string, unknown>;
  setClipText(wf, '2', positive);
  setClipText(wf, '3', negative);
  if (opts.ckpt_name) {
    setCkptName(wf, '1', opts.ckpt_name);
  }
  if (typeof opts.seed === 'number' && Number.isFinite(opts.seed)) {
    setKsamplerSeed(wf, '5', Math.floor(opts.seed));
  }
  return wf;
}

function injectSdxl(
  base: Record<string, unknown>,
  positive: string,
  negative: string,
  opts: { ckpt_name?: string; seed?: number },
): Record<string, unknown> {
  const wf = JSON.parse(JSON.stringify(base)) as Record<string, unknown>;
  setClipText(wf, '6', positive);
  setClipText(wf, '7', negative);
  if (opts.ckpt_name) {
    setCkptName(wf, '4', opts.ckpt_name);
  }
  if (typeof opts.seed === 'number' && Number.isFinite(opts.seed)) {
    setKsamplerSeed(wf, '3', Math.floor(opts.seed));
  }
  return wf;
}

/**
 * POST /api/image/generate-zimage
 *
 * Body: { prompt, negative?, ckpt_name?, seed?, priority? }
 * Graph: zimage_txt2img.v1.graph.json — CLIP nodes 2/3, CheckpointLoaderSimple 1, KSampler 5
 */
imageGenerationRouter.post('/generate-zimage', async (req: Request, res: Response) => {
  if (!queueService) {
    return res.status(503).json({ error: 'Queue service not initialized' });
  }

  const { prompt, negative, ckpt_name, seed, priority } = req.body ?? {};

  if (!prompt || typeof prompt !== 'string' || prompt.length === 0) {
    return res.status(400).json({ error: 'prompt is required (non-empty string)' });
  }

  try {
    const base = loadWorkflowFile('zimage_txt2img.v1.graph.json');
    const neg = typeof negative === 'string' && negative.length > 0 ? negative : DEFAULT_NEG_ZIMAGE;
    const wf = injectZImage(base, prompt, neg, {
      ckpt_name: typeof ckpt_name === 'string' && ckpt_name.length > 0 ? ckpt_name : undefined,
      seed: typeof seed === 'number' ? seed : undefined,
    });

    const comfyPromptId = await submitComfyPrompt(wf, 'gen_zimage_txt2img');
    const prio = typeof priority === 'number' ? priority : 0;
    const jobId = queueService.enqueue('zimage_txt2img', prio);
    const job = queueService.get(jobId);

    return res.status(201).json({
      job_id: jobId,
      comfy_prompt_id: comfyPromptId,
      status: job?.status ?? 'pending',
      model: 'zimage_txt2img',
      estimated_duration_seconds: 45,
      status_path: `/generation/queue/${jobId}`,
    });
  } catch (err) {
    console.error('[image-generation] zimage:', err);
    const message = err instanceof Error ? err.message : 'Unknown error';
    return res.status(500).json({ error: `Failed to generate image: ${message}` });
  }
});

/**
 * POST /api/image/generate-sdxl
 *
 * Body: { prompt, negative?, ckpt_name?, seed?, priority? }
 * Graph: sdxl_txt2img.v1.graph.json — CyberRealistic XL skeleton; CLIP 6/7, ckpt 4, KSampler 3
 */
imageGenerationRouter.post('/generate-sdxl', async (req: Request, res: Response) => {
  if (!queueService) {
    return res.status(503).json({ error: 'Queue service not initialized' });
  }

  const { prompt, negative, ckpt_name, seed, priority } = req.body ?? {};

  if (!prompt || typeof prompt !== 'string' || prompt.length === 0) {
    return res.status(400).json({ error: 'prompt is required (non-empty string)' });
  }

  try {
    const base = loadWorkflowFile('sdxl_txt2img.v1.graph.json');
    const neg = typeof negative === 'string' && negative.length > 0 ? negative : DEFAULT_NEG_SDXL;
    const wf = injectSdxl(base, prompt, neg, {
      ckpt_name: typeof ckpt_name === 'string' && ckpt_name.length > 0 ? ckpt_name : undefined,
      seed: typeof seed === 'number' ? seed : undefined,
    });

    const comfyPromptId = await submitComfyPrompt(wf, 'gen_sdxl_txt2img');
    const prio = typeof priority === 'number' ? priority : 0;
    const jobId = queueService.enqueue('sdxl_txt2img', prio);
    const job = queueService.get(jobId);

    return res.status(201).json({
      job_id: jobId,
      comfy_prompt_id: comfyPromptId,
      status: job?.status ?? 'pending',
      model: 'sdxl_txt2img',
      estimated_duration_seconds: 90,
      status_path: `/generation/queue/${jobId}`,
    });
  } catch (err) {
    console.error('[image-generation] sdxl:', err);
    const message = err instanceof Error ? err.message : 'Unknown error';
    return res.status(500).json({ error: `Failed to generate image: ${message}` });
  }
});

imageGenerationRouter.get('/status/:jobId', (req: Request, res: Response) => {
  if (!queueService) {
    return res.status(503).json({ error: 'Queue service not initialized' });
  }

  try {
    const job = queueService.get(req.params.jobId);
    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    return res.json({
      ...job,
      estimated_remaining_seconds: job.status === 'running' ? 60 : null,
    });
  } catch (err) {
    console.error('[image-generation] status:', err);
    return res.status(500).json({ error: 'Failed to get job status' });
  }
});
