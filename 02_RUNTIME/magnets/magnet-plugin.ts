/**
 * Extensible magnet plugin interface (TypeScript runtime).
 */

import { MagnetReport } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';
import { BaseMagnet } from './base-magnet';
import { ConfidenceMagnet } from './confidence-magnet';
import { CostMagnet } from './cost-magnet';
import { ExecutionMagnet } from './execution-magnet';

export interface MagnetPlugin {
  readonly id: string;
  readonly magnetType: MagnetReport['magnet_type'];
  report(): MagnetReport;
  reset(): void;
}

export class BaseMagnetPluginAdapter implements MagnetPlugin {
  constructor(
    private readonly magnet: BaseMagnet,
    public readonly id: string
  ) {}

  get magnetType(): MagnetReport['magnet_type'] {
    return this.magnet.magnet_type;
  }

  report(): MagnetReport {
    return this.magnet.report();
  }

  reset(): void {
    this.magnet.reset();
  }
}

export class MagnetPluginRegistry {
  private static globalInstance: MagnetPluginRegistry | null = null;
  private plugins = new Map<string, MagnetPlugin>();

  static global(): MagnetPluginRegistry {
    if (!MagnetPluginRegistry.globalInstance) {
      MagnetPluginRegistry.globalInstance = createDefaultRuntimeRegistry();
    }
    return MagnetPluginRegistry.globalInstance;
  }

  static resetGlobal(): void {
    MagnetPluginRegistry.globalInstance = null;
  }

  register(plugin: MagnetPlugin, options?: { replace?: boolean }): void {
    if (this.plugins.has(plugin.id) && !options?.replace) {
      throw new Error(`magnet already registered: ${plugin.id}`);
    }
    this.plugins.set(plugin.id, plugin);
  }

  unregister(id: string): void {
    this.plugins.delete(id);
  }

  get(id: string): MagnetPlugin | undefined {
    return this.plugins.get(id);
  }

  list(): string[] {
    return Array.from(this.plugins.keys()).sort();
  }

  collectReports(): MagnetReport[] {
    return Array.from(this.plugins.values()).map((p) => p.report());
  }

  resetAll(): void {
    for (const plugin of this.plugins.values()) {
      plugin.reset();
    }
  }
}

export function createDefaultRuntimeRegistry(
  costBudget?: { tokens: number; tool_calls: number }
): MagnetPluginRegistry {
  const registry = new MagnetPluginRegistry();
  registry.register(new BaseMagnetPluginAdapter(new ExecutionMagnet(), 'execution'));
  registry.register(
    new BaseMagnetPluginAdapter(
      new CostMagnet(costBudget || { tokens: 100000, tool_calls: 100 }),
      'cost'
    )
  );
  registry.register(new BaseMagnetPluginAdapter(new ConfidenceMagnet(), 'confidence'));
  return registry;
}
