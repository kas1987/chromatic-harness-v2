import { Router, Request, Response } from 'express';
import type { GenerationQueueService, JobStatus } from '../services/generation-queue-service';

export const generationQueueRouter = Router();

let queueService: GenerationQueueService | null = null;

export function initializeGenerationQueueRouter(service: GenerationQueueService): void {
  queueService = service;
}

const VALID_STATUSES = new Set<JobStatus>(['pending', 'running', 'completed', 'failed']);

// GET /generation/queue — list jobs, optionally filtered by status
generationQueueRouter.get('/', (req: Request, res: Response) => {
  if (!queueService) {
    return res.json([]);
  }
  try {
    const status = req.query.status as JobStatus | undefined;
    const limit = req.query.limit ? parseInt(req.query.limit as string, 10) : 100;
    if (status && !VALID_STATUSES.has(status)) {
      return res.status(400).json({ error: `Invalid status. Must be one of: ${[...VALID_STATUSES].join(', ')}` });
    }
    const jobs = queueService.list(status, limit);
    return res.json(jobs);
  } catch (err) {
    console.error('[generation-queue] list error:', err);
    return res.json([]);
  }
});

// POST /generation/queue — enqueue a new job
generationQueueRouter.post('/', (req: Request, res: Response) => {
  if (!queueService) {
    return res.status(503).json({ error: 'Queue service not initialized' });
  }
  const { script_name, priority } = req.body ?? {};
  if (!script_name || typeof script_name !== 'string') {
    return res.status(400).json({ error: 'script_name is required' });
  }
  const prio = typeof priority === 'number' ? priority : 0;
  try {
    const id = queueService.enqueue(script_name, prio);
    const job = queueService.get(id);
    return res.status(201).json(job);
  } catch (err) {
    console.error('[generation-queue] enqueue error:', err);
    return res.status(500).json({ error: 'Failed to enqueue job' });
  }
});

// GET /generation/queue/:jobId — get job details
generationQueueRouter.get('/:jobId', (req: Request, res: Response) => {
  if (!queueService) {
    return res.status(503).json({ error: 'Queue service not initialized' });
  }
  try {
    const job = queueService.get(req.params.jobId);
    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }
    return res.json(job);
  } catch (err) {
    console.error('[generation-queue] get error:', err);
    return res.status(500).json({ error: 'Failed to get job' });
  }
});

// PUT /generation/queue/:jobId — update job status
generationQueueRouter.put('/:jobId', (req: Request, res: Response) => {
  if (!queueService) {
    return res.status(503).json({ error: 'Queue service not initialized' });
  }
  const { status, failure_reason } = req.body ?? {};
  if (!status || !VALID_STATUSES.has(status)) {
    return res.status(400).json({ error: `status must be one of: ${[...VALID_STATUSES].join(', ')}` });
  }
  try {
    const job = queueService.get(req.params.jobId);
    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }
    switch (status as JobStatus) {
      case 'running':
        queueService.markRunning(req.params.jobId);
        break;
      case 'completed':
        queueService.markCompleted(req.params.jobId);
        break;
      case 'failed':
        queueService.markFailed(req.params.jobId, failure_reason ?? 'Unknown error');
        break;
      default:
        return res.status(400).json({ error: `Cannot set status to '${status}' via this endpoint` });
    }
    const updated = queueService.get(req.params.jobId);
    return res.json(updated);
  } catch (err) {
    console.error('[generation-queue] update error:', err);
    return res.status(500).json({ error: 'Failed to update job' });
  }
});
