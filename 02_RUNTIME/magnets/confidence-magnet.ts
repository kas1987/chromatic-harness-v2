/**
 * Confidence Magnet
 *
 * Scores how confident we should be in the execution result:
 * - Test coverage and pass rate
 * - Code quality (lint results, type checking)
 * - Review signals (human approval, quality gates)
 * - Evidence of correctness (documentation, comments)
 */

import { BaseMagnet } from './base-magnet';
import { TestResult } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';
import { analyzeTestPyramid, type PyramidAnalysis } from './test_pyramid';

export class ConfidenceMagnet extends BaseMagnet {
  private testResults: TestResult[] = [];
  private lintIssues: { level: string; message: string; file: string }[] = [];
  private typeCheckPassed = true;
  private hasReviewApproval = false;
  private documentationQuality = 0; // 0-1
  private codeCommentRatio = 0; // 0-1
  private pyramidAnalysis: PyramidAnalysis | null = null;
  private pyramidPenalty = 0;

  constructor() {
    super('confidence');
  }

  /**
   * Record test results
   */
  onTestResults(results: TestResult[]): void {
    this.testResults.push(...results);

    const passed = results.filter((r) => r.status === 'pass').length;
    const total = results.length;
    const passRate = passed / Math.max(1, total);

    if (passRate < 0.8) {
      this.raiseAnomaly(
        'warn',
        `Low test pass rate: ${passed}/${total} (${(passRate * 100).toFixed(1)}%)`,
        {
          passed,
          total,
          pass_rate: passRate,
        },
        'Investigate failing tests before merge'
      );
    }

    if (total === 0) {
      this.raiseAnomaly(
        'warn',
        'No tests ran',
        { test_count: 0 },
        'Add tests or verify test discovery'
      );
    }

    this.observe('tests_passed', passed);
    this.observe('tests_total', total);
    this.observe('test_pass_rate', passRate);

    this.pyramidAnalysis = analyzeTestPyramid(results);
    this.observe('test_pyramid', {
      counts: this.pyramidAnalysis.counts,
      ratios: this.pyramidAnalysis.ratios,
      targets: this.pyramidAnalysis.targets,
      balanced: this.pyramidAnalysis.balanced,
    });

    for (const warning of this.pyramidAnalysis.warnings) {
      const isError = warning.includes('imbalance') || warning.includes('inverted');
      this.raiseAnomaly(
        isError ? 'warn' : 'info',
        warning,
        {
          counts: this.pyramidAnalysis.counts,
          ratios: this.pyramidAnalysis.ratios,
          max_deviation: this.pyramidAnalysis.max_deviation,
        },
        'Rebalance tests toward unit-heavy pyramid (70/20/10)'
      );
    }

    if (this.pyramidAnalysis.max_deviation >= 0.25) {
      this.pyramidPenalty = 0.08;
    } else if (this.pyramidAnalysis.max_deviation >= 0.15) {
      this.pyramidPenalty = 0.03;
    } else {
      this.pyramidPenalty = 0;
    }
  }

  /**
   * Record linting issues
   */
  onLintIssues(issues: { level: string; message: string; file: string }[]): void {
    this.lintIssues.push(...issues);

    const errors = issues.filter((i) => i.level === 'error').length;
    const warnings = issues.filter((i) => i.level === 'warning').length;

    if (errors > 0) {
      this.raiseAnomaly(
        'error',
        `Linting errors found: ${errors} error(s)`,
        {
          error_count: errors,
          warning_count: warnings,
          issues: issues.slice(0, 3), // Show first 3
        },
        'Fix linting errors before merge'
      );
    } else if (warnings > 5) {
      this.raiseAnomaly(
        'warn',
        `Many lint warnings: ${warnings}`,
        {
          warning_count: warnings,
        },
        'Consider addressing lint warnings'
      );
    }

    this.observe('lint_errors', errors);
    this.observe('lint_warnings', warnings);
  }

  /**
   * Record type checking result
   */
  onTypeCheckResult(passed: boolean, errorCount: number = 0): void {
    this.typeCheckPassed = passed;

    if (!passed) {
      this.raiseAnomaly(
        'error',
        `Type checking failed: ${errorCount} error(s)`,
        {
          type_errors: errorCount,
        },
        'Resolve type errors before merge'
      );
    }

    this.observe('type_check_passed', passed);
    this.observe('type_errors', errorCount);
  }

  /**
   * Record that code passed review
   */
  onReviewApproval(approvedBy?: string): void {
    this.hasReviewApproval = true;
    this.observe('review_approved', true);
    this.observe('reviewed_by', approvedBy);
  }

  /**
   * Record code quality metrics
   */
  onCodeQuality(metrics: {
    comment_ratio?: number; // 0-1
    documentation_quality?: number; // 0-1
    cyclomatic_complexity?: number;
  }): void {
    if (metrics.comment_ratio !== undefined) {
      this.codeCommentRatio = metrics.comment_ratio;
      if (metrics.comment_ratio < 0.1) {
        this.raiseAnomaly(
          'info',
          `Low code comment ratio: ${(metrics.comment_ratio * 100).toFixed(1)}%`,
          { comment_ratio: metrics.comment_ratio },
          'Consider adding explanatory comments'
        );
      }
    }

    if (metrics.documentation_quality !== undefined) {
      this.documentationQuality = metrics.documentation_quality;
      if (metrics.documentation_quality < 0.5) {
        this.raiseAnomaly(
          'warn',
          `Poor documentation quality`,
          { quality_score: metrics.documentation_quality },
          'Add API docs and usage examples'
        );
      }
    }

    if (metrics.cyclomatic_complexity !== undefined && metrics.cyclomatic_complexity > 15) {
      this.raiseAnomaly(
        'warn',
        `High cyclomatic complexity: ${metrics.cyclomatic_complexity}`,
        { complexity: metrics.cyclomatic_complexity },
        'Consider breaking into smaller functions'
      );
    }

    this.observe('code_metrics', metrics);
  }

  /**
   * Custom score: composite of all signals
   */
  protected calculateScore(): number {
    let score = 0.5; // Start at baseline

    // Test coverage weight (40%)
    if (this.testResults.length > 0) {
      const passRate = this.testResults.filter((r) => r.status === 'pass').length / this.testResults.length;
      score += passRate * 0.4;
    } else {
      score -= 0.1; // Penalty for no tests
    }

    // Type checking weight (20%)
    if (this.typeCheckPassed) {
      score += 0.2;
    } else {
      score -= 0.15;
    }

    // Lint weight (15%)
    if (this.lintIssues.length === 0) {
      score += 0.15;
    } else {
      const errorCount = this.lintIssues.filter((i) => i.level === 'error').length;
      score -= Math.min(0.15, (errorCount * 0.05 + this.lintIssues.length * 0.01));
    }

    // Code quality weight (15%)
    const avgQuality = (this.documentationQuality + Math.min(1, this.codeCommentRatio * 2)) / 2;
    score += avgQuality * 0.15;

    // Review approval bonus
    if (this.hasReviewApproval) {
      score += 0.1;
    }

    score -= this.pyramidPenalty;

    // Penalize anomalies
    for (const anomaly of this.anomalies) {
      if (anomaly.level === 'error') score -= 0.1;
      else if (anomaly.level === 'warn') score -= 0.02;
    }

    return Math.max(0, Math.min(1, score));
  }

  /**
   * Get confidence summary
   */
  getSummary(): {
    test_pass_rate: number;
    type_check_passed: boolean;
    lint_clean: boolean;
    review_approved: boolean;
    overall_confidence: number;
  } {
    const testPassRate =
      this.testResults.length === 0
        ? 0
        : this.testResults.filter((r) => r.status === 'pass').length / this.testResults.length;

    return {
      test_pass_rate: testPassRate,
      type_check_passed: this.typeCheckPassed,
      lint_clean: this.lintIssues.length === 0,
      review_approved: this.hasReviewApproval,
      overall_confidence: this.calculateScore(),
    };
  }

  reset(): void {
    super.reset();
    this.testResults = [];
    this.lintIssues = [];
    this.typeCheckPassed = true;
    this.hasReviewApproval = false;
    this.documentationQuality = 0;
    this.codeCommentRatio = 0;
    this.pyramidAnalysis = null;
    this.pyramidPenalty = 0;
  }
}
