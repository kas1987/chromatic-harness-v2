import { Router, Request, Response } from 'express';
import fs from 'fs';
import path from 'path';
import type { GenerationQueueService } from '../services/generation-queue-service';
import type { ComfyEventBridge } from '../core/comfy-event-bridge';

export const videoGenerationRouter = Router();

let queueService: GenerationQueueService | null = null;
let comfyBridge: ComfyEventBridge | null = null;
const comfyUrl = process.env.GEN_COMFY_URL || 'http://127.0.0.1:8188';

/**
 * Initialize the video generation router with required services
 */
export function initializeVideoGenerationRouter(
  queue: GenerationQueueService | null,
  bridge: ComfyEventBridge | null
): void {
  queueService = queue;
  comfyBridge = bridge;
}

/**
 * Load workflow JSON from file system
 * @param type Either 'txt2vid' or 'img2vid'
 * @returns Parsed workflow object
 */
function loadWorkflow(type: 'txt2vid' | 'img2vid'): Record<string, unknown> {
  const projectRoot = path.resolve(process.cwd(), 'Image-Prism');
  const workflowPath = path.join(
    projectRoot,
    'apps/metachromatic/comfy/workflows',
    `wan_${type}.v1.graph.json`
  );

  if (!fs.existsSync(workflowPath)) {
    throw new Error(`Workflow not found: ${workflowPath}`);
  }

  const content = fs.readFileSync(workflowPath, 'utf-8');
  return JSON.parse(content);
}

/**
 * Substitute placeholders in workflow with user values
 */
function injectPrompt(
  workflow: Record<string, unknown>,
  type: 'txt2vid' | 'img2vid',
  prompt: string,
  imagePath?: string
): Record<string, unknown> {
  const wf = JSON.parse(JSON.stringify(workflow)); // Deep copy

  if (type === 'txt2vid') {
    // For T2V: inject prompt into CLIPTextEncode nodes (nodes 2 and 3)
    // Node 2 = positive prompt, Node 3 = negative
    if (wf['2'] && typeof wf['2'] === 'object') {
      const node = wf['2'] as Record<string, unknown>;
      if (node.inputs && typeof node.inputs === 'object') {
        (node.inputs as Record<string, unknown>).text = prompt;
      }
    }
  } else if (type === 'img2vid') {
    // For I2V: inject motion description into positive prompt (node 4)
    if (wf['4'] && typeof wf['4'] === 'object') {
      const node = wf['4'] as Record<string, unknown>;
      if (node.inputs && typeof node.inputs === 'object') {
        (node.inputs as Record<string, unknown>).text = prompt;
      }
    }

    // Inject image path into LoadImage node (node 11)
    if (imagePath) {
      if (wf['11'] && typeof wf['11'] === 'object') {
        const node = wf['11'] as Record<string, unknown>;
        if (node.inputs && typeof node.inputs === 'object') {
          (node.inputs as Record<string, unknown>).image = imagePath;
        }
      }
    }
  }

  return wf;
}

/**
 * Submit workflow to ComfyUI API
 */
async function submitToComfyUI(workflow: Record<string, unknown>): Promise<string> {
  const payload = JSON.stringify({
    prompt: workflow,
    client_id: 'wan_video_gen',
  });

  try {
    const response = await fetch(`${comfyUrl}/prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
    });

    if (!response.ok) {
      throw new Error(`ComfyUI API error: ${response.status} ${response.statusText}`);
    }

    const data = (await response.json()) as { prompt_id: string };
    return data.prompt_id;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const wrapped = new Error(`Failed to submit to ComfyUI: ${message}`);
    Object.assign(wrapped, { cause: err });
    throw wrapped;
  }
}

/**
 * POST /video/generate-wan
 *
 * Submit a WAN video generation job.
 *
 * Request body:
 * {
 *   "type": "txt2vid" | "img2vid",
 *   "prompt": "video description or motion description",
 *   "image_path": "optional image file name (required for img2vid)",
 *   "priority": 0 (optional)
 * }
 *
 * Response:
 * {
 *   "job_id": "uuid",
 *   "comfy_prompt_id": "comfyui-prompt-id",
 *   "status": "pending",
 *   "type": "txt2vid" | "img2vid",
 *   "estimated_duration_seconds": 240,
 *   "status_path": "/generation/queue/{job_id}"
 * }
 */
videoGenerationRouter.post('/generate-wan', async (req: Request, res: Response) => {
  if (!queueService) {
    return res.status(503).json({ error: 'Queue service not initialized' });
  }

  const { type, prompt, image_path, priority } = req.body ?? {};

  // Validate required fields
  if (!type || !['txt2vid', 'img2vid'].includes(type)) {
    return res.status(400).json({ error: 'type must be "txt2vid" or "img2vid"' });
  }

  if (!prompt || typeof prompt !== 'string' || prompt.length === 0) {
    return res.status(400).json({ error: 'prompt is required (non-empty string)' });
  }

  if (type === 'img2vid' && !image_path) {
    return res.status(400).json({ error: 'image_path is required for img2vid' });
  }

  try {
    // Load and inject workflow
    const baseWorkflow = loadWorkflow(type);
    const injectedWorkflow = injectPrompt(baseWorkflow, type, prompt, image_path);

    // Submit to ComfyUI
    const comfyPromptId = await submitToComfyUI(injectedWorkflow);

    // Create queue entry for tracking
    const scriptName = `wan_${type}`;
    const prio = typeof priority === 'number' ? priority : 0;
    const jobId = queueService.enqueue(scriptName, prio);

    // Store mapping of job_id → comfy_prompt_id somewhere (for now, just return it)
    // In a real implementation, you'd store this in the queue DB or a separate mapping
    const job = queueService.get(jobId);

    return res.status(201).json({
      job_id: jobId,
      comfy_prompt_id: comfyPromptId,
      status: job?.status ?? 'pending',
      type,
      estimated_duration_seconds: 240, // ~4 minutes per spec
      status_path: `/generation/queue/${jobId}`,
    });
  } catch (err) {
    console.error('[video-generation] Error:', err);
    const message = err instanceof Error ? err.message : 'Unknown error';
    return res.status(500).json({ error: `Failed to generate video: ${message}` });
  }
});

/**
 * GET /video/status/:jobId
 *
 * Get status of a WAN video generation job (convenience endpoint, same as /generation/queue/:jobId)
 *
 * Response:
 * {
 *   "id": "job-uuid",
 *   "script_name": "wan_txt2vid" | "wan_img2vid",
 *   "status": "pending" | "running" | "completed" | "failed",
 *   "priority": 0,
 *   "failure_reason": null | "error message",
 *   "created_at": "ISO timestamp",
 *   "updated_at": "ISO timestamp"
 * }
 */
videoGenerationRouter.get('/status/:jobId', (req: Request, res: Response) => {
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
      estimated_remaining_seconds: job.status === 'running' ? 180 : null,
    });
  } catch (err) {
    console.error('[video-generation] Status error:', err);
    return res.status(500).json({ error: 'Failed to get job status' });
  }
});
