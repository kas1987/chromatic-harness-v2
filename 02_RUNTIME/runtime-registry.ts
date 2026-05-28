/**
 * Runtime Registry
 *
 * Maintains a map of available runtimes and factory to instantiate them.
 * CMP uses this to route missions to the appropriate executor.
 */

import { RuntimeAdapter, RuntimeCapabilities } from '../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';
import { RoachPiAdapter } from './adapters/roach-pi-adapter';

export interface RuntimeRegistryConfig {
  [runtime_id: string]: {
    adapter: new (...args: any[]) => RuntimeAdapter;
    config: Record<string, any>;
  };
}

export class RuntimeRegistry {
  private adapters: Map<string, RuntimeAdapter> = new Map();
  private config: RuntimeRegistryConfig;

  constructor(config: RuntimeRegistryConfig) {
    this.config = config;
  }

  /**
   * Initialize all registered runtimes
   */
  async initialize(): Promise<void> {
    for (const [runtime_id, { adapter: AdapterClass, config }] of Object.entries(this.config)) {
      const instance = new AdapterClass(config);
      this.adapters.set(runtime_id, instance);
    }
  }

  /**
   * Get a runtime adapter by ID
   */
  getRuntime(runtime_id: string): RuntimeAdapter | undefined {
    return this.adapters.get(runtime_id);
  }

  /**
   * List all available runtimes
   */
  listRuntimes(): RuntimeAdapter[] {
    return Array.from(this.adapters.values());
  }

  /**
   * Get capabilities of a specific runtime
   */
  getCapabilities(runtime_id: string): RuntimeCapabilities | undefined {
    const runtime = this.getRuntime(runtime_id);
    return runtime?.capabilities();
  }

  /**
   * Find best-fit runtime for a given mission
   * (Simple heuristic; could be more sophisticated)
   */
  async findBestRuntime(intent: string, scope: string[]): Promise<RuntimeAdapter | undefined> {
    for (const runtime of this.listRuntimes()) {
      if (await runtime.canHandle(intent, scope)) {
        return runtime;
      }
    }
    return undefined;
  }

  /**
   * Shutdown all runtimes
   */
  async shutdown(): Promise<void> {
    for (const runtime of this.listRuntimes()) {
      await runtime.shutdown();
    }
    this.adapters.clear();
  }
}

/**
 * Default registry configuration
 * Update this with your actual runtime configs
 */
export const DEFAULT_REGISTRY_CONFIG: RuntimeRegistryConfig = {
  'roach-pi': {
    adapter: RoachPiAdapter,
    config: {
      base_branch: 'main',
      repo_path: process.env.REPO_PATH || './repo',
      timeout_seconds: 1800,
      retry_strategy: 'exponential',
    },
  },
  // 'langraph': { ... },
  // 'openhands': { ... },
};
