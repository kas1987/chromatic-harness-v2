/**
 * roach-pi submodule resolution and scope guards.
 */

import * as fs from 'fs';
import * as path from 'path';

export type RoachPiMode = 'stub' | 'submodule';

export interface ScopeValidation {
  valid: boolean;
  errors: string[];
  warnings: string[];
  normalized: string[];
}

const HEALTH_MARKERS = [
  'extensions/agentic-harness/package.json',
  'extensions/agentic-harness/index.ts',
];

export function resolveRepoRoot(explicit?: string): string {
  if (explicit) return path.resolve(explicit);
  let here = path.resolve(__dirname);
  for (let i = 0; i < 10; i++) {
    if (
      fs.existsSync(path.join(here, '00_SOURCE_OF_TRUTH')) ||
      fs.existsSync(path.join(here, '.git'))
    ) {
      return here;
    }
    const parent = path.dirname(here);
    if (parent === here) break;
    here = parent;
  }
  return process.cwd();
}

export function defaultRoachPiRoot(repoRoot?: string): string {
  const root = resolveRepoRoot(repoRoot);
  return path.join(root, '02_RUNTIME', 'runtime-engines', 'roach-pi');
}

export function submoduleHealthy(roachRoot: string): boolean {
  return HEALTH_MARKERS.every((rel) => fs.existsSync(path.join(roachRoot, rel)));
}

export function detectMode(roachRoot?: string, repoRoot?: string): { mode: RoachPiMode; root: string } {
  const envRoot = process.env.ROACH_PI_ROOT;
  const root = path.resolve(envRoot || roachRoot || defaultRoachPiRoot(repoRoot));
  if (submoduleHealthy(root)) {
    return { mode: 'submodule', root };
  }
  return { mode: 'stub', root };
}

/** Reject path traversal and paths outside repo_root. */
export function validateScopePaths(scope: string[], repoRoot: string): ScopeValidation {
  const errors: string[] = [];
  const warnings: string[] = [];
  const normalized: string[] = [];
  const repoResolved = path.resolve(repoRoot);

  for (const raw of scope) {
    const trimmed = (raw || '').trim();
    if (!trimmed) {
      warnings.push('empty scope entry skipped');
      continue;
    }
    if (trimmed.includes('..')) {
      errors.push(`scope path must not contain '..': ${trimmed}`);
      continue;
    }
    if (path.isAbsolute(trimmed)) {
      errors.push(`scope path must be relative: ${trimmed}`);
      continue;
    }
    const resolved = path.resolve(repoResolved, trimmed);
    if (!resolved.startsWith(repoResolved + path.sep) && resolved !== repoResolved) {
      errors.push(`scope escapes repo root: ${trimmed}`);
      continue;
    }
    normalized.push(trimmed.replace(/\\/g, '/'));
  }

  if (normalized.length === 0 && errors.length === 0) {
    errors.push('scope must have at least one valid path');
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    normalized,
  };
}

export function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms);
    promise
      .then((v) => {
        clearTimeout(timer);
        resolve(v);
      })
      .catch((err) => {
        clearTimeout(timer);
        reject(err);
      });
  });
}
