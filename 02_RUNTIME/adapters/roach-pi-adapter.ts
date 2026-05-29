/**
 * roach-pi Runtime Adapter
 *
 * Wraps the roach-pi agentic harness to speak the Chromatic Harness protocol.
 * Translates MissionPackets into roach-pi tasks, collects telemetry via Magnets,
 * and normalizes results back to Chromatic format.
 */

import {
  RuntimeAdapter,
  MissionPacket,
  ExecutionResult,
  RuntimeCapabilities,
  ValidationResult,
  ExecutionError,
  Task,
  ToolCall,
  Artifact,
  Learning,
  MagnetReport,
  TestResult,
} from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';
import { ExecutionMagnet } from '../magnets/execution-magnet';
import { CostMagnet } from '../magnets/cost-magnet';
import { ConfidenceMagnet } from '../magnets/confidence-magnet';
import { MagnetSynthesis } from '../magnets/magnet-synthesis';
import {
  detectMode,
  resolveRepoRoot,
  validateScopePaths,
  withTimeout,
  type RoachPiMode,
} from './roach-pi-loader';

/**
 * roach-pi-specific configuration
 */
interface RoachPiConfig {
  base_branch: string;
  repo_path: string;
  timeout_seconds: number;
  retry_strategy: 'exponential' | 'linear';
  roach_pi_root?: string;
}

/**
 * Adapter for roach-pi runtime
 */
export class RoachPiAdapter implements RuntimeAdapter {
  readonly runtime_id = 'roach-pi';
  readonly runtime_name = 'roach-pi agentic harness';

  private config: RoachPiConfig;
  private repoRoot: string;
  private runtimeMode: RoachPiMode;
  private roachPiRoot: string;
  private roachPi: any; // Loaded when submodule is present
  private executionLog: ToolCall[] = [];
  private magnetReports: MagnetReport[] = [];

  // Magnets for observability
  private executionMagnet: ExecutionMagnet;
  private costMagnet: CostMagnet;
  private confidenceMagnet: ConfidenceMagnet;
  private synthesis: MagnetSynthesis;

  constructor(config: RoachPiConfig) {
    this.config = config;
    this.repoRoot = resolveRepoRoot(config.repo_path);
    const detected = detectMode(config.roach_pi_root, this.repoRoot);
    this.runtimeMode = detected.mode;
    this.roachPiRoot = detected.root;
    // Initialize magnets
    this.executionMagnet = new ExecutionMagnet();
    this.costMagnet = new CostMagnet({ tokens: 100000, tool_calls: 100 });
    this.confidenceMagnet = new ConfidenceMagnet();
    this.synthesis = new MagnetSynthesis();
    if (this.runtimeMode === 'submodule') {
      // Future: dynamic import from submodule entry (extensions/agentic-harness)
      this.roachPi = { root: this.roachPiRoot, mode: 'submodule' };
    }
  }

  getRuntimeMode(): RoachPiMode {
    return this.runtimeMode;
  }

  async executeMission(packet: MissionPacket): Promise<ExecutionResult> {
    const startTime = Date.now();

    try {
      // Reset magnets for this mission
      this.resetMagnets();
      this.magnetReports = [];

      // 1. Validate packet shape
      const validation = await this.validate(packet);
      if (!validation.valid) {
        throw new Error(`Mission packet validation failed: ${validation.errors.join(', ')}`);
      }

      // Initialize cost magnet with this mission's budget
      this.costMagnet = new CostMagnet(packet.budget);

      const scopeCheck = validateScopePaths(packet.scope, this.repoRoot);
      if (!scopeCheck.valid) {
        throw new Error(`Scope validation failed: ${scopeCheck.errors.join(', ')}`);
      }

      // 2. Translate MissionPacket → roach-pi task format
      const roachTask = this.translateMission(packet, scopeCheck.normalized);

      // 3. Wrap task with Magnet hooks (collect observability)
      const wrappedTask = this.wrapWithMagnets(roachTask);

      // 4. Execute via roach-pi (submodule when present, else stub)
      const timeoutMs = Math.max(30, this.config.timeout_seconds) * 1000;
      const roachResult = await withTimeout(
        this.executeWrapped(wrappedTask),
        timeoutMs,
        'roach-pi mission'
      );

      // 5. Collect magnet data from execution
      await this.collectMagnetData(roachResult);

      // 6. Synthesize magnet reports
      this.magnetReports = [
        this.executionMagnet.report(),
        this.costMagnet.report(),
        this.confidenceMagnet.report(),
      ];
      this.synthesis.addReport(this.magnetReports[0]);
      this.synthesis.addReport(this.magnetReports[1]);
      this.synthesis.addReport(this.magnetReports[2]);

      // 7. Normalize output to Chromatic format
      const result: ExecutionResult = {
        mission_id: packet.mission_id,
        status: roachResult.success ? 'success' : 'failed',
        output: {
          closed_tasks: roachResult.closed_tasks || [],
          blocked_tasks: roachResult.blocked_tasks || [],
          created_artifacts: roachResult.artifacts || [],
        },
        telemetry: {
          tokens_used: roachResult.tokens_used || 0,
          tool_calls_count: this.executionLog.length,
          tool_calls: this.executionLog,
          errors: roachResult.errors || [],
          retries: roachResult.retry_count || 0,
          duration_ms: Date.now() - startTime,
          test_results: roachResult.test_results || [],
        },
        learnings: roachResult.learnings || [],
        magnet_reports: this.magnetReports,
        runtime_info: {
          mode: this.runtimeMode,
          roach_pi_root: this.roachPiRoot,
        },
      };

      return result;
    } catch (error) {
      throw new Error(`roach-pi execution failed: ${(error as Error).message}`);
    }
  }

  async canHandle(intent: string, scope: string[]): Promise<boolean> {
    // roach-pi is best for code-driven workflows
    const codeKeywords = ['code', 'feature', 'bug', 'test', 'refactor', 'pr', 'commit'];
    const isCodeTask = codeKeywords.some((kw) => intent.toLowerCase().includes(kw));
    return isCodeTask && scope.length > 0;
  }

  async validate(packet: MissionPacket): Promise<ValidationResult> {
    const errors: string[] = [];
    const warnings: string[] = [];

    if (!packet.mission_id) errors.push('mission_id is required');
    if (!packet.intent || packet.intent.length < 10) errors.push('intent must be at least 10 characters');
    if (packet.agent_framework !== 'roach-pi') errors.push('agent_framework must be "roach-pi"');
    const scopeCheck = validateScopePaths(packet.scope || [], this.repoRoot);
    if (!scopeCheck.valid) errors.push(...scopeCheck.errors);
    warnings.push(...scopeCheck.warnings);
    if (packet.budget.tokens < 1000) warnings.push('tokens budget is very low (<1000)');
    if (packet.budget.tool_calls < 5) warnings.push('tool_calls budget is very low (<5)');

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  }

  capabilities(): RuntimeCapabilities {
    return {
      supported_frameworks: ['roach-pi'],
      max_token_budget: 500000,
      max_tool_calls: 500,
      supported_tool_categories: ['file', 'repo', 'shell', 'test', 'lint', 'git'],
      can_parallelize: false, // roach-pi is sequential
      can_recover_from_errors: true,
      can_test_output: true,
      sandbox_max_level: 5, // roach-pi is fully trusted (T5)
    };
  }

  async shutdown(): Promise<void> {
    // TODO: Cleanup roach-pi resources
    // await this.roachPi.shutdown();
  }

  /**
   * Reset all magnets for a new mission
   */
  private resetMagnets(): void {
    this.executionMagnet.reset();
    this.costMagnet.reset();
    this.confidenceMagnet.reset();
    this.synthesis.reset();
    this.executionLog = [];
    this.magnetReports = [];
  }

  /**
   * Collect magnet data from execution result
   */
  private async collectMagnetData(roachResult: any): Promise<void> {
    // ExecutionMagnet: tool calls and errors
    if (roachResult.tool_calls) {
      for (const toolCall of roachResult.tool_calls) {
        this.executionMagnet.onToolCall(toolCall);
      }
    }

    if (roachResult.errors) {
      for (const error of roachResult.errors) {
        this.executionMagnet.onError(error);
      }
    }

    // CostMagnet: token usage and tool call budget
    if (roachResult.tokens_used) {
      this.costMagnet.onTokensUsed(roachResult.tokens_used);
    }

    if (roachResult.tool_calls) {
      for (const _ of roachResult.tool_calls) {
        this.costMagnet.onToolInvocation();
      }
    }

    this.costMagnet.checkWallTimeBudget();

    // ConfidenceMagnet: test results, code quality
    if (roachResult.test_results) {
      this.confidenceMagnet.onTestResults(roachResult.test_results);
    }

    if (roachResult.lint_issues) {
      this.confidenceMagnet.onLintIssues(roachResult.lint_issues);
    }

    if (roachResult.type_check_passed !== undefined) {
      this.confidenceMagnet.onTypeCheckResult(
        roachResult.type_check_passed,
        roachResult.type_errors || 0
      );
    }

    if (roachResult.reviewed_by) {
      this.confidenceMagnet.onReviewApproval(roachResult.reviewed_by);
    }

    if (roachResult.code_quality) {
      this.confidenceMagnet.onCodeQuality(roachResult.code_quality);
    }
  }

  /**
   * Convert MissionPacket to roach-pi task format
   */
  private async executeWrapped(task: any): Promise<any> {
    if (this.runtimeMode === 'submodule' && this.roachPi) {
      // Placeholder until submodule execute API is wired
      return this.mockExecute(task);
    }
    return this.mockExecute(task);
  }

  private translateMission(packet: MissionPacket, scope: string[]): any {
    return {
      id: packet.mission_id,
      title: packet.intent,
      scope,
      runtime_mode: this.runtimeMode,
      roach_pi_root: this.roachPiRoot,
      budget: packet.budget,
      // Map Chromatic gates → roach-pi validation stages
      validation_stages: this.mapGates(packet.required_gates),
      metadata: packet.metadata || {},
    };
  }

  /**
   * Map CMP gates to roach-pi validation stages
   */
  private mapGates(gates: string[]): string[] {
    const mapping: Record<string, string> = {
      intent: 'task_clarification',
      scope: 'scope_validation',
      confidence: 'review_confidence',
    };
    return gates.map((gate) => mapping[gate] || gate);
  }

  /**
   * Wrap task with Magnet hooks to collect observability
   */
  private wrapWithMagnets(task: any): any {
    const self = this;

    // Would inject hooks like:
    // task.onToolCall = (tool, args) => { self.executionLog.push(...); }
    // task.onError = (error) => { self.handleError(error); }
    // task.onTestResult = (result) => { self.handleTestResult(result); }

    return task;
  }

  /**
   * Mock execution for Phase 2 testing with real magnet data
   */
  private async mockExecute(task: any): Promise<any> {
    // Simulate tool calls for ExecutionMagnet
    const mockToolCalls: ToolCall[] = [
      {
        tool_name: 'file_read',
        arguments: { path: 'src/components/Hero.tsx' },
        result: { lines: 245 },
        duration_ms: 45,
        timestamp: Date.now(),
        error: undefined,
        retry_count: 0,
      },
      {
        tool_name: 'file_write',
        arguments: { path: 'src/components/Hero.tsx', content: '...' },
        result: { bytes_written: 8234 },
        duration_ms: 120,
        timestamp: Date.now() + 100,
        error: undefined,
        retry_count: 0,
      },
      {
        tool_name: 'git_commit',
        arguments: { message: 'Add dark mode styles' },
        result: { commit_sha: 'abc123' },
        duration_ms: 85,
        timestamp: Date.now() + 250,
        error: undefined,
        retry_count: 0,
      },
    ];

    // Simulate test results for ConfidenceMagnet
    const mockTestResults: TestResult[] = [
      { test_name: 'test_user_model', status: 'pass', duration_ms: 40 },
      { test_name: 'test_scope_gate', status: 'pass', duration_ms: 35 },
      { test_name: 'test_confidence_score', status: 'pass', duration_ms: 30 },
      { test_name: 'api_integration_smoke', status: 'pass', duration_ms: 120 },
      { test_name: 'api_integration_db', status: 'pass', duration_ms: 95 },
      { test_name: 'dark_mode_e2e', status: 'pass', duration_ms: 250, suite_path: 'tests/e2e/' },
    ];

    // Store tool calls for execution log
    this.executionLog = mockToolCalls;

    return {
      success: true,
      closed_tasks: [
        {
          id: 'task-1',
          title: 'Implement dark mode feature',
          status: 'completed',
          evidence: { pr_merged: true, tests_passed: 3 },
        },
      ],
      blocked_tasks: [],
      artifacts: [
        {
          type: 'pr',
          name: 'Add dark mode support',
          url: 'https://github.com/example/pull/123',
        },
      ],
      tool_calls: mockToolCalls,
      tokens_used: 45000,
      errors: [],
      retry_count: 0,
      test_results: mockTestResults,
      type_check_passed: true,
      type_errors: 0,
      lint_issues: [],
      reviewed_by: 'alice@example.com',
      code_quality: {
        comment_ratio: 0.15,
        documentation_quality: 0.8,
        cyclomatic_complexity: 8,
      },
      learnings: [
        {
          title: 'CSS utility pattern found',
          detail: 'Dark mode can be implemented efficiently with CSS variables',
          tags: ['css', 'dark-mode', 'performance'],
          confidence: 0.9,
        },
        {
          title: 'Test coverage improved',
          detail: 'Added tests increased coverage from 78% to 85%',
          tags: ['testing', 'coverage'],
          confidence: 0.95,
        },
      ],
    };
  }

  /**
   * Handle execution errors and report to Magnets
   */
  private async handleError(error: ExecutionError): Promise<void> {
    // TODO: Update confidence/security magnets
    // if (error.code === 'INJECTION_DETECTED') { ... escalate ... }
  }
}
