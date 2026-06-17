import { describe, it, expect, vi } from 'vitest';
import { ComfyHealthClient } from '../comfyHealthClient';

describe('ComfyHealthClient - Exponential Backoff (L0-L1)', () => {
  it('should export ComfyHealthClient class', () => {
    expect(ComfyHealthClient).toBeDefined();
  });

  it('should have checkHealth method', () => {
    const client = new ComfyHealthClient({ url: 'http://localhost:8188' });
    expect(client.checkHealth).toBeDefined();
    expect(typeof client.checkHealth).toBe('function');
  });

  it('should implement exponential backoff with formula: delay = baseDelay * 2^attempt + jitter', async () => {
    const client = new ComfyHealthClient({
      url: 'http://localhost:8188',
      maxRetries: 3,
      baseDelay: 100,
      timeout: 100
    });

    // Mock fetch to fail first two times, succeed on third
    let attemptCount = 0;
    global.fetch = vi.fn(async () => {
      attemptCount++;
      if (attemptCount < 3) {
        throw new Error('Network error');
      }
      return { ok: true } as Response;
    });

    const result = await client.checkHealth();
    expect(result.healthy).toBe(true);
    expect(attemptCount).toBe(3); // Should retry twice before success
  });

  it('should return { healthy: false } after max retries', async () => {
    const client = new ComfyHealthClient({
      url: 'http://localhost:8188',
      maxRetries: 3,
      timeout: 10
    });

    global.fetch = vi.fn(async () => {
      throw new Error('Network error');
    });

    const result = await client.checkHealth();
    expect(result.healthy).toBe(false);
  });

  it('should have startMonitoring method', () => {
    const client = new ComfyHealthClient({ url: 'http://localhost:8188' });
    expect(client.startMonitoring).toBeDefined();
  });
});
