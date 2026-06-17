/**
 * Delegate Job Queue — backpressure and priority scheduling for /api/delegate.
 *
 * Problem it solves:
 *   Multiple concurrent workflows (ComfyUI generation + LLM hooks) can burst-fire
 *   delegate requests simultaneously. Without a queue, every request that lands when
 *   all provider slots are occupied immediately returns 503. That drops work silently
 *   and forces callers to implement their own retry — which creates thundering-herd
 *   on recovery.
 *
 * Solution:
 *   Accept every job into an in-process priority queue. Process jobs in priority order
 *   as provider slots become available. Callers await their result (still synchronous
 *   from their perspective). Jobs that exceed the per-job timeout or the max queue
 *   depth are rejected with a clear capacity signal, not a silent 503.
 *
 * Priority levels:
 *   "high"   — interactive requests (user waiting on a response)
 *   "normal" — workflow/hook-driven requests (ComfyUI generation pipeline)
 *   "low"    — batch/background tasks (calibration, overnight sweeps)
 *
 * Flow:
 *   caller → enqueue(job, priority) → [queue] → dispatch(job) when slot opens → resolve
 *
 * Capacity integration:
 *   The queue holds the ProviderCapacityTracker reference and only dispatches jobs
 *   when at least one provider in the fallback chain has an open slot. This avoids
 *   dispatching a job that will immediately exhaust every provider and return 503.
 *
 * Backpressure:
 *   MAX_QUEUE_DEPTH (default 50): hard cap on pending + in-flight jobs.
 *   If exceeded, enqueue() rejects immediately with a clear error — callers can
 *   back off and retry. Never silently drops.
 */

import type { ProviderCapacityTracker } from "./provider-capacity.js";
import type { LlmProvider } from "../llm/llm-types.js";

export type JobPriority = "high" | "normal" | "low";

export interface QueuedJob {
  id: string;
  priority: JobPriority;
  enqueuedAt: number;
  timeoutMs: number;
  execute: () => Promise<unknown>;
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
}

export interface QueueStats {
  pending: number;
  inFlight: number;
  totalAccepted: number;
  totalCompleted: number;
  totalFailed: number;
  totalTimedOut: number;
  byPriority: Record<JobPriority, number>;
  capacitySnapshot?: Record<LlmProvider, { inFlight: number; maxSlots: number; atCapacity: boolean }>;
}

const PRIORITY_ORDER: Record<JobPriority, number> = { high: 0, normal: 1, low: 2 };

/** Default limits — tuned for a single workstation running ComfyUI concurrently */
const MAX_QUEUE_DEPTH = 50;
const DEFAULT_JOB_TIMEOUT_MS = 60_000; // 60s — long enough for slow models
const DISPATCH_POLL_MS = 100; // how often to check for new slots when queue has jobs

export class DelegateQueue {
  private queue: QueuedJob[] = [];
  private inFlight = 0;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private stats = {
    totalAccepted: 0,
    totalCompleted: 0,
    totalFailed: 0,
    totalTimedOut: 0,
  };

  constructor(
    private readonly capacity: ProviderCapacityTracker,
    private readonly maxDepth = MAX_QUEUE_DEPTH,
    private readonly pollMs = DISPATCH_POLL_MS,
  ) {
    this.startPoller();
  }

  /**
   * Enqueue a delegation job. Returns a promise that resolves with the job's result
   * once a provider slot becomes available and the job completes.
   *
   * Rejects immediately if:
   *   - Queue depth is at max (backpressure signal — caller should back off)
   *   - Job timeout expires before dispatch
   */
  enqueue<T>(
    execute: () => Promise<T>,
    options: {
      priority?: JobPriority;
      timeoutMs?: number;
      jobId?: string;
    } = {},
  ): Promise<T> {
    const depth = this.queue.length + this.inFlight;
    if (depth >= this.maxDepth) {
      return Promise.reject(
        new QueueCapacityError(
          `Delegate queue at capacity (${depth}/${this.maxDepth} jobs). Back off and retry.`,
          depth,
          this.maxDepth,
        ),
      );
    }

    const priority = options.priority ?? "normal";
    const timeoutMs = options.timeoutMs ?? DEFAULT_JOB_TIMEOUT_MS;
    const id = options.jobId ?? `dq-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

    let resolveOuter!: (value: T) => void;
    let rejectOuter!: (reason: unknown) => void;
    const promise = new Promise<T>((resolve, reject) => {
      resolveOuter = resolve;
      rejectOuter = reject;
    });

    // Timeout watchdog — fires if job sits in queue + execute too long
    const timeoutHandle = setTimeout(() => {
      const idx = this.queue.findIndex((j) => j.id === id);
      if (idx !== -1) {
        this.queue.splice(idx, 1);
        this.stats.totalTimedOut++;
        rejectOuter(new JobTimeoutError(`Job ${id} timed out after ${timeoutMs}ms in queue`));
      }
    }, timeoutMs);

    const job: QueuedJob = {
      id,
      priority,
      enqueuedAt: Date.now(),
      timeoutMs,
      execute: execute as () => Promise<unknown>,
      resolve: (v) => {
        clearTimeout(timeoutHandle);
        resolveOuter(v as T);
      },
      reject: (r) => {
        clearTimeout(timeoutHandle);
        rejectOuter(r);
      },
    };

    this.insertSorted(job);
    this.stats.totalAccepted++;
    return promise;
  }

  /** Snapshot of queue state for monitoring/status endpoints. */
  getStats(): QueueStats {
    const byPriority: Record<JobPriority, number> = { high: 0, normal: 0, low: 0 };
    for (const j of this.queue) byPriority[j.priority]++;
    return {
      pending: this.queue.length,
      inFlight: this.inFlight,
      ...this.stats,
      byPriority,
      capacitySnapshot: this.capacity.getSnapshot(),
    };
  }

  /** Drain remaining jobs with rejection (called on server shutdown). */
  drain(reason = "Server shutting down"): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
    for (const job of this.queue) {
      job.reject(new Error(reason));
    }
    this.queue = [];
  }

  // --------------------------------------------------------------------------
  // Private
  // --------------------------------------------------------------------------

  /** Insert into queue maintaining priority order (stable sort on enqueue time within tier). */
  private insertSorted(job: QueuedJob): void {
    let i = this.queue.length;
    while (i > 0 && PRIORITY_ORDER[this.queue[i - 1].priority] > PRIORITY_ORDER[job.priority]) {
      i--;
    }
    this.queue.splice(i, 0, job);
  }

  /**
   * Dispatch loop: runs every DISPATCH_POLL_MS and fires off pending jobs
   * whenever the capacity tracker shows at least one provider has an open slot.
   *
   * We don't dispatch more than `availableSlots` jobs per tick to avoid
   * over-saturating on a burst of capacity becoming available simultaneously.
   */
  private startPoller(): void {
    this.pollTimer = setInterval(() => {
      if (this.queue.length === 0) return;

      // Count providers with at least one open slot — dispatch at most that many jobs
      // per tick so we never over-saturate a single provider with unroutable work.
      const snapshot = this.capacity.getSnapshot();
      const providersWithSlots = Object.values(snapshot).filter(
        (s) => s.maxSlots - s.inFlight > 0,
      ).length;

      if (providersWithSlots <= 0) return;

      // Dispatch at most one job per provider that has capacity this tick
      const toDispatch = Math.min(providersWithSlots, this.queue.length);
      for (let i = 0; i < toDispatch; i++) {
        const job = this.queue.shift();
        if (!job) break;
        this.dispatch(job);
      }
    }, this.pollMs);

    // Don't let this timer prevent Node process from exiting
    if (this.pollTimer.unref) this.pollTimer.unref();
  }

  private dispatch(job: QueuedJob): void {
    this.inFlight++;
    job
      .execute()
      .then((result) => {
        this.inFlight--;
        this.stats.totalCompleted++;
        job.resolve(result);
      })
      .catch((err) => {
        this.inFlight--;
        this.stats.totalFailed++;
        job.reject(err);
      });
  }
}

// ---------------------------------------------------------------------------
// Custom errors — callers can instanceof-check for queue-specific failures
// ---------------------------------------------------------------------------

export class QueueCapacityError extends Error {
  constructor(
    message: string,
    public readonly currentDepth: number,
    public readonly maxDepth: number,
  ) {
    super(message);
    this.name = "QueueCapacityError";
  }
}

export class JobTimeoutError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "JobTimeoutError";
  }
}
