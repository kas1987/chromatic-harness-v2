/**
 * ComfyUI Health Client with Exponential Backoff
 *
 * Provides automated health checks to ComfyUI with exponential backoff retry logic.
 * Implements the formula: delay = baseDelay * 2^attempt + jitter
 */

export interface ComfyHealthClientOptions {
  url: string;
  maxRetries?: number;
  baseDelay?: number; // ms
  timeout?: number; // ms
}

export interface HealthCheckResult {
  healthy: boolean;
  latency?: number;
  error?: string;
}

export class ComfyHealthClient {
  private url: string;
  private maxRetries: number;
  private baseDelay: number;
  private timeout: number;

  constructor(options: ComfyHealthClientOptions) {
    this.url = options.url;
    this.maxRetries = options.maxRetries ?? 3;
    this.baseDelay = options.baseDelay ?? 1000;
    this.timeout = options.timeout ?? getDefaultComfyHealthTimeoutMs();
  }

  /**
   * Check ComfyUI health with exponential backoff.
   * Formula: delay = baseDelay * 2^attempt + jitter
   *
   * @returns Promise resolving to health check result
   */
  async checkHealth(): Promise<HealthCheckResult> {
    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const start = Date.now();
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);
        let response: Response;
        try {
          response = await fetch(`${this.url}/system`, {
            method: "GET",
            signal: controller.signal,
          });
        } finally {
          clearTimeout(timeoutId);
        }

        if (response.ok) {
          return {
            healthy: true,
            latency: Date.now() - start,
          };
        }
      } catch (e) {
        const error = e instanceof Error ? e.message : String(e);

        if (attempt < this.maxRetries - 1) {
          // Exponential backoff with jitter
          const jitter = Math.random() * 1000;
          const delay =
            this.baseDelay * Math.pow(2, attempt) + jitter;
          await sleep(delay);
        } else {
          return {
            healthy: false,
            error: `All ${this.maxRetries} health check attempts failed: ${error}`,
          };
        }
      }
    }

    return {
      healthy: false,
      error: `Health check failed after ${this.maxRetries} attempts`,
    };
  }

  /**
   * Start continuous health monitoring.
   * Returns AbortController to stop monitoring.
   *
   * @param intervalMs - Interval between checks (default 30000ms)
   * @returns AbortController to stop monitoring
   */
  startMonitoring(intervalMs: number = 30000): AbortController {
    const controller = new AbortController();

    const loop = async () => {
      while (!controller.signal.aborted) {
        try {
          await this.checkHealth();
        } catch (e) {
          // Log but don't crash monitoring loop
          console.error('[ComfyUI Health]', e);
        }

        // Wait before next check
        await sleep(intervalMs);
      }
    };

    // Start loop in background
    loop().catch((e) => console.error('[ComfyUI Health] Monitoring loop crashed:', e));

    return controller;
  }
}

/**
 * Sleep utility for delays.
 * @param ms - Milliseconds to sleep
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getDefaultComfyHealthTimeoutMs(): number {
  const raw = process.env.COMFY_HEALTH_TIMEOUT_MS;
  if (!raw) {
    return 10000;
  }

  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 10000;
  }

  return Math.max(1000, Math.floor(parsed));
}
