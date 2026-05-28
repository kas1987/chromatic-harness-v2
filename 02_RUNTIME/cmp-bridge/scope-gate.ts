/**
 * Scope Gate
 *
 * Validates that the allowed file scope is:
 * - Not empty (must have at least one path)
 * - Specific enough (not overly broad like '/')
 * - Realistic (paths exist or will be created)
 * - Doesn't violate forbidden paths (config, secrets, etc.)
 */

import { MissionPacket } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';

export interface ScopeGateResult {
  passed: boolean;
  coverage_score: number; // 0-1
  issues: string[];
  warnings: string[];
  forbidden_conflicts: string[];
}

export class ScopeGate {
  private forbiddenPaths = [
    '.env',
    '.secrets',
    'config/secrets',
    'private/',
    'credentials/',
    '.git/hooks',
    'node_modules/.bin',
    'package-lock.json', // Should review before modifying
    'yarn.lock',
    '/etc/',
    '/root/',
  ];

  /**
   * Evaluate scope validity
   */
  evaluate(packet: MissionPacket): ScopeGateResult {
    const issues: string[] = [];
    const warnings: string[] = [];
    const forbidden_conflicts: string[] = [];
    let score = 1.0;

    // Check 1: Scope is not empty
    if (!packet.scope || packet.scope.length === 0) {
      issues.push('Scope is empty');
      score -= 0.5;
    }

    // Check 2: Scope is not overly broad
    const broadPaths = packet.scope.filter((p) => p === '/' || p === './' || p === '');
    if (broadPaths.length > 0) {
      issues.push('Scope is too broad (/ or .)');
      score -= 0.3;
    }

    // Check 3: Scope doesn't include system paths
    const systemPaths = packet.scope.filter((p) => p.startsWith('/') && !p.startsWith('./'));
    if (systemPaths.length > 0) {
      warnings.push(`System paths in scope: ${systemPaths.join(', ')}`);
      score -= 0.15;
    }

    // Check 4: Scope doesn't conflict with forbidden paths
    for (const forbidden of this.forbiddenPaths) {
      for (const allowed of packet.scope) {
        if (allowed.includes(forbidden) || forbidden.includes(allowed)) {
          forbidden_conflicts.push(`"${allowed}" conflicts with forbidden path "${forbidden}"`);
          score -= 0.2;
        }
      }
    }

    // Check 5: Scope is reasonable size (not too fragmented)
    if (packet.scope.length > 20) {
      warnings.push('Scope includes >20 paths; consider consolidating');
      score -= 0.1;
    }

    // Check 6: Scope paths are consistent (no overlaps)
    for (let i = 0; i < packet.scope.length; i++) {
      for (let j = i + 1; j < packet.scope.length; j++) {
        const p1 = packet.scope[i];
        const p2 = packet.scope[j];
        if (p1.includes(p2) || p2.includes(p1)) {
          warnings.push(`Overlapping scope paths: "${p1}" includes "${p2}"`);
        }
      }
    }

    score = Math.max(0, Math.min(1, score));

    return {
      passed: score >= 0.6 && forbidden_conflicts.length === 0,
      coverage_score: Math.round(score * 100) / 100,
      issues,
      warnings,
      forbidden_conflicts,
    };
  }

  /**
   * Generate human-readable feedback
   */
  formatResult(result: ScopeGateResult): string {
    const lines: string[] = [];
    lines.push(`Scope Coverage: ${(result.coverage_score * 100).toFixed(0)}%`);

    if (result.forbidden_conflicts.length > 0) {
      lines.push('\n🚫 Forbidden Conflicts (must resolve):');
      for (const conflict of result.forbidden_conflicts) {
        lines.push(`  • ${conflict}`);
      }
    }

    if (result.issues.length > 0) {
      lines.push('\n⚠️ Issues:');
      for (const issue of result.issues) {
        lines.push(`  • ${issue}`);
      }
    }

    if (result.warnings.length > 0) {
      lines.push('\n💡 Warnings:');
      for (const warning of result.warnings) {
        lines.push(`  • ${warning}`);
      }
    }

    const verdict = result.passed ? '✓ PASS' : '✗ FAIL';
    lines.push(`\nVerdict: ${verdict}`);

    return lines.join('\n');
  }

  /**
   * Add a forbidden path
   */
  addForbiddenPath(path: string): void {
    this.forbiddenPaths.push(path);
  }

  /**
   * Remove a forbidden path
   */
  removeForbiddenPath(path: string): void {
    const idx = this.forbiddenPaths.indexOf(path);
    if (idx >= 0) {
      this.forbiddenPaths.splice(idx, 1);
    }
  }
}
