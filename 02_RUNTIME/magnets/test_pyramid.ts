/**
 * Test pyramid ratio analysis (unit / integration / e2e).
 */

import { TestResult } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';

export type TestLayer = 'unit' | 'integration' | 'e2e';

export interface PyramidTargets {
  unit: number;
  integration: number;
  e2e: number;
}

export const DEFAULT_PYRAMID_TARGETS: PyramidTargets = {
  unit: 0.7,
  integration: 0.2,
  e2e: 0.1,
};

export interface PyramidAnalysis {
  total: number;
  counts: Record<TestLayer, number>;
  ratios: Record<TestLayer, number>;
  targets: PyramidTargets;
  deviations: Record<TestLayer, number>;
  max_deviation: number;
  warnings: string[];
  balanced: boolean;
}

function isE2e(blob: string, path: string): boolean {
  if (/[/\\]e2e[/\\]/i.test(path)) return true;
  const b = blob.toLowerCase();
  return ['e2e', 'end-to-end', 'end_to_end', 'playwright', 'cypress', 'selenium', 'browser'].some(
    (t) => b.includes(t)
  );
}

function isIntegration(blob: string, path: string): boolean {
  if (/[/\\]integration[/\\]/i.test(path)) return true;
  const b = blob.toLowerCase();
  return ['integration', 'api_test', 'api-test', 'contract_test', 'contract-test'].some((t) =>
    b.includes(t)
  );
}

export function classifyTest(test: TestResult): TestLayer {
  if (test.layer === 'unit' || test.layer === 'integration' || test.layer === 'e2e') {
    return test.layer;
  }
  const name = test.test_name || '';
  const path = test.suite_path || '';
  const blob = `${path} ${name}`;
  if (isE2e(blob, path)) {
    return 'e2e';
  }
  if (isIntegration(blob, path)) {
    return 'integration';
  }
  return 'unit';
}

export function analyzeTestPyramid(
  results: TestResult[],
  targets: PyramidTargets = DEFAULT_PYRAMID_TARGETS,
  options: { warn_threshold?: number; error_threshold?: number } = {}
): PyramidAnalysis {
  const warn_threshold = options.warn_threshold ?? 0.15;
  const error_threshold = options.error_threshold ?? 0.25;
  const active = results.filter((r) => r.status !== 'skip');
  const counts: Record<TestLayer, number> = { unit: 0, integration: 0, e2e: 0 };

  for (const test of active) {
    counts[classifyTest(test)] += 1;
  }

  const total = active.length;
  const ratios: Record<TestLayer, number> = {
    unit: total ? counts.unit / total : 0,
    integration: total ? counts.integration / total : 0,
    e2e: total ? counts.e2e / total : 0,
  };

  const deviations: Record<TestLayer, number> = {
    unit: Math.abs(ratios.unit - targets.unit),
    integration: Math.abs(ratios.integration - targets.integration),
    e2e: Math.abs(ratios.e2e - targets.e2e),
  };

  const max_deviation = Math.max(deviations.unit, deviations.integration, deviations.e2e);
  const warnings: string[] = [];

  if (total === 0) {
    warnings.push('Test pyramid: no runnable tests to classify');
    return {
      total: 0,
      counts,
      ratios,
      targets,
      deviations,
      max_deviation: 0,
      warnings,
      balanced: false,
    };
  }

  const pct = (n: number) => `${(n * 100).toFixed(0)}%`;
  const layers: TestLayer[] = ['unit', 'integration', 'e2e'];

  for (const layer of layers) {
    const dev = deviations[layer];
    const actual = ratios[layer];
    const target = targets[layer];
    if (dev >= error_threshold) {
      warnings.push(
        `Test pyramid imbalance (${layer}): actual ${pct(actual)} vs target ${pct(target)} (Δ ${pct(dev)})`
      );
    } else if (dev >= warn_threshold) {
      warnings.push(
        `Test pyramid drift (${layer}): actual ${pct(actual)} vs target ${pct(target)}`
      );
    }
  }

  if (counts.e2e > counts.unit && total >= 3) {
    warnings.push('Test pyramid inverted: more e2e than unit tests');
  }

  return {
    total,
    counts,
    ratios,
    targets,
    deviations,
    max_deviation,
    warnings,
    balanced: warnings.length === 0,
  };
}
