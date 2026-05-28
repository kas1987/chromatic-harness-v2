/**
 * Sandbox Validator
 *
 * Validates agent behavior at each sandbox level.
 * Detects violations and escalates.
 */

import {
  SandboxLevel,
  AgentBehavior,
  SANDBOX_LEVEL_NAMES,
} from './sandbox-types';

export interface ValidationResult {
  level: SandboxLevel;
  passed: boolean;
  violations: string[];
  warnings: string[];
  confidence_score: number;
}

export class SandboxValidator {
  /**
   * Validate behavior at a specific level
   */
  validate(behavior: AgentBehavior): ValidationResult {
    const violations: string[] = [];
    const warnings: string[] = [];
    let confidence = 0.9; // Start high, deduct for violations

    switch (behavior.level) {
      case 0:
        this.validateL0(behavior, violations, warnings, confidence);
        break;
      case 1:
        this.validateL1(behavior, violations, warnings, confidence);
        break;
      case 2:
        this.validateL2(behavior, violations, warnings, confidence);
        break;
      case 3:
        this.validateL3(behavior, violations, warnings, confidence);
        break;
      case 4:
        this.validateL4(behavior, violations, warnings, confidence);
        break;
      case 5:
        this.validateL5(behavior, violations, warnings, confidence);
        break;
    }

    // Adjust confidence for violations
    confidence -= violations.length * 0.15;
    confidence -= warnings.length * 0.05;
    confidence -= behavior.errors * 0.1;
    confidence -= behavior.scope_violations * 0.2;

    confidence = Math.max(0, Math.min(1, confidence));

    return {
      level: behavior.level,
      passed: violations.length === 0,
      violations,
      warnings,
      confidence_score: confidence,
    };
  }

  /**
   * L0: Dry run validation
   * Agent should NOT call any tools, only reason
   */
  private validateL0(
    behavior: AgentBehavior,
    violations: string[],
    warnings: string[],
    _confidence: number
  ): void {
    if (behavior.tool_calls > 0) {
      violations.push(
        `L0 violation: Agent made ${behavior.tool_calls} tool call(s) in dry-run mode`
      );
    }

    if (behavior.execution_time_ms > 30000) {
      warnings.push('L0 warning: Reasoning took >30s (possible loop or inefficiency)');
    }
  }

  /**
   * L1: Read-only validation
   * Agent can read but not write. Must stay within scope.
   */
  private validateL1(
    behavior: AgentBehavior,
    violations: string[],
    warnings: string[],
    _confidence: number
  ): void {
    // Check for writes
    if (behavior.observations['write_attempts']?.length > 0) {
      violations.push(
        `L1 violation: Agent attempted writes in read-only mode: ${behavior.observations['write_attempts'].join(', ')}`
      );
    }

    // Check scope violations
    if (behavior.scope_violations > 0) {
      violations.push(`L1 violation: Agent violated scope ${behavior.scope_violations} time(s)`);
    }

    // Check file reads
    if (behavior.tool_calls > 50) {
      warnings.push(
        `L1 warning: Agent made ${behavior.tool_calls} file reads (may be exploring inefficiently)`
      );
    }

    if (behavior.errors > 2) {
      warnings.push(`L1 warning: ${behavior.errors} errors during read-only exploration`);
    }
  }

  /**
   * L2: Simulated patch validation
   * Agent can modify files but only in patch copies, no merge
   */
  private validateL2(
    behavior: AgentBehavior,
    violations: string[],
    warnings: string[],
    _confidence: number
  ): void {
    // Check for merge attempts
    if (behavior.observations['merge_attempts']?.length > 0) {
      violations.push(
        `L2 violation: Agent attempted merge in simulated mode. Merge attempts: ${behavior.observations['merge_attempts'].join(', ')}`
      );
    }

    // Check scope violations
    if (behavior.scope_violations > 0) {
      violations.push(`L2 violation: Agent modified files outside scope (${behavior.scope_violations})`);
    }

    // Check patch quality
    if (behavior.test_pass_rate < 0.5) {
      warnings.push(
        `L2 warning: Patch quality low (${(behavior.test_pass_rate * 100).toFixed(0)}% tests pass)`
      );
    }

    if (behavior.errors > 1) {
      violations.push(`L2 violation: Too many errors during patch creation (${behavior.errors})`);
    }
  }

  /**
   * L3: Sandboxed container validation
   * Agent can execute in isolated container, but not merge to main
   */
  private validateL3(
    behavior: AgentBehavior,
    violations: string[],
    warnings: string[],
    _confidence: number
  ): void {
    // Check for main branch changes
    if (behavior.observations['attempted_main_branch']?.length > 0) {
      violations.push('L3 violation: Agent attempted changes to main branch');
    }

    // Check test results
    if (behavior.test_pass_rate < 0.7) {
      warnings.push(
        `L3 warning: Low test pass rate (${(behavior.test_pass_rate * 100).toFixed(0)}%)`
      );
    }

    // Check execution reliability
    if (behavior.errors > 2) {
      violations.push(`L3 violation: Too many runtime errors (${behavior.errors})`);
    }

    if (behavior.execution_time_ms > 120000) {
      warnings.push('L3 warning: Execution took >2 minutes (possible inefficiency)');
    }
  }

  /**
   * L4: Draft PR validation
   * Agent creates real branches/PRs but cannot merge without approval
   */
  private validateL4(
    behavior: AgentBehavior,
    violations: string[],
    warnings: string[],
    _confidence: number
  ): void {
    // Check for unauthorized merges
    if (behavior.observations['unauthorized_merge']?.length > 0) {
      violations.push('L4 violation: Agent performed merge without approval');
    }

    // Check PR quality
    if (behavior.test_pass_rate < 0.8) {
      warnings.push(
        `L4 warning: PR quality concern (${(behavior.test_pass_rate * 100).toFixed(0)}% tests)`
      );
    }

    // Check for scope issues
    if (behavior.scope_violations > 0) {
      warnings.push(`L4 warning: PR touches files outside declared scope (${behavior.scope_violations})`);
    }

    // High error count
    if (behavior.errors > 3) {
      violations.push(`L4 violation: Too many errors in PR (${behavior.errors})`);
    }
  }

  /**
   * L5: Trusted validation
   * Agent has full autonomy but should have high quality bar
   */
  private validateL5(
    behavior: AgentBehavior,
    violations: string[],
    warnings: string[],
    _confidence: number
  ): void {
    // L5 agents are trusted, but we still watch for regression
    if (behavior.test_pass_rate < 0.85) {
      warnings.push(
        `L5 alert: Trusted agent test pass rate dropped to ${(behavior.test_pass_rate * 100).toFixed(0)}%`
      );
    }

    if (behavior.errors > 5) {
      violations.push(`L5 alert: Unusual error rate for trusted agent (${behavior.errors} errors)`);
    }

    // Scope violations are less acceptable for trusted agents
    if (behavior.scope_violations > 0) {
      warnings.push('L5 alert: Trusted agent had scope violations');
    }
  }

  /**
   * Detect level-specific violations
   */
  detectViolations(
    behavior: AgentBehavior
  ): {
    violations: string[];
    severity: 'info' | 'warn' | 'error';
    should_demote: boolean;
  } {
    const result = this.validate(behavior);

    let severity: 'info' | 'warn' | 'error' = 'info';
    let should_demote = false;

    if (result.violations.length > 0) {
      severity = 'error';
      should_demote = result.level > 0; // Demote if violations at non-L0
    } else if (result.warnings.length > 0) {
      severity = 'warn';
    }

    return {
      violations: [...result.violations, ...result.warnings],
      severity,
      should_demote,
    };
  }

  /**
   * Generate formatted validation report
   */
  formatValidation(result: ValidationResult): string {
    const lines: string[] = [];

    lines.push(`═════════════════════════════════════`);
    lines.push(`Sandbox Level ${result.level}: ${SANDBOX_LEVEL_NAMES[result.level]}`);
    lines.push(`═════════════════════════════════════`);
    lines.push('');

    const verdict = result.passed ? '✅ PASSED' : '❌ FAILED';
    lines.push(verdict);
    lines.push(`Confidence: ${(result.confidence_score * 100).toFixed(0)}%`);
    lines.push('');

    if (result.violations.length > 0) {
      lines.push('🔴 Violations:');
      for (const violation of result.violations) {
        lines.push(`  • ${violation}`);
      }
      lines.push('');
    }

    if (result.warnings.length > 0) {
      lines.push('🟡 Warnings:');
      for (const warning of result.warnings) {
        lines.push(`  • ${warning}`);
      }
      lines.push('');
    }

    if (result.violations.length === 0 && result.warnings.length === 0) {
      lines.push('✓ No violations or warnings detected');
      lines.push('');
    }

    lines.push('═════════════════════════════════════');

    return lines.join('\n');
  }
}
