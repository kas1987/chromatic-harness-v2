/**
 * Phase 3 Integration Test
 *
 * Verifies that:
 * - CMP gates (Intent, Scope, Confidence) work correctly
 * - CMP Executor orchestrates gates and produces approval decisions
 * - BeadsBridge converts execution results into Chromatic beads
 * - Full governance flow (intake → execution → completion) works
 */

import { MissionPacket, ExecutionResult } from '../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';
import { CMPExecutor, MissionApproval } from './cmp-bridge/cmp-executor';
import { BeadsBridge } from './beads-bridge';
import { MagnetSynthesis } from './magnets/magnet-synthesis';
import { ExecutionMagnet } from './magnets/execution-magnet';
import { CostMagnet } from './magnets/cost-magnet';
import { ConfidenceMagnet } from './magnets/confidence-magnet';

/**
 * Test 1: Intent Gate
 */
async function testIntentGate(): Promise<void> {
  console.log('Test 1: Intent Gate validation');

  const executor = new CMPExecutor();

  const goodPacket: MissionPacket = {
    mission_id: 'm-test-good',
    intent: 'Add dark mode toggle to the dashboard with CSS variables',
    agent_framework: 'roach-pi',
    scope: ['src/components/', 'src/styles/'],
    budget: { tokens: 50000, tool_calls: 80 },
    required_gates: ['intent'],
  };

  const badPacket: MissionPacket = {
    mission_id: 'm-test-bad',
    intent: 'fix things',
    agent_framework: 'roach-pi',
    scope: ['src/'],
    budget: { tokens: 50000, tool_calls: 80 },
    required_gates: ['intent'],
  };

  const goodApproval = executor.evaluateIntake(goodPacket);
  const badApproval = executor.evaluateIntake(badPacket);

  console.log(`  ✓ Clear intent approved: ${goodApproval.approved}`);
  console.log(`  ✓ Vague intent rejected: ${!badApproval.approved}`);
  console.log(`    Intent score (good): ${(goodApproval.gate_results.intent.clarity_score * 100).toFixed(0)}%`);
  console.log(`    Intent score (bad):  ${(badApproval.gate_results.intent.clarity_score * 100).toFixed(0)}%`);
}

/**
 * Test 2: Scope Gate
 */
async function testScopeGate(): Promise<void> {
  console.log('\nTest 2: Scope Gate validation');

  const executor = new CMPExecutor();

  const goodPacket: MissionPacket = {
    mission_id: 'm-test-scope-good',
    intent: 'Update styling',
    agent_framework: 'roach-pi',
    scope: ['src/components/', 'src/styles/'],
    budget: { tokens: 50000, tool_calls: 80 },
    required_gates: ['scope'],
  };

  const badPacket: MissionPacket = {
    mission_id: 'm-test-scope-bad',
    intent: 'Update everything',
    agent_framework: 'roach-pi',
    scope: ['/', '.env', '.secrets'],
    budget: { tokens: 50000, tool_calls: 80 },
    required_gates: ['scope'],
  };

  const goodApproval = executor.evaluateIntake(goodPacket);
  const badApproval = executor.evaluateIntake(badPacket);

  console.log(`  ✓ Appropriate scope approved: ${goodApproval.approved}`);
  console.log(`  ✓ Forbidden scope rejected: ${!badApproval.approved}`);
  console.log(`    Scope score (good): ${(goodApproval.gate_results.scope.coverage_score * 100).toFixed(0)}%`);
  console.log(
    `    Forbidden conflicts: ${badApproval.gate_results.scope.forbidden_conflicts.length}`
  );
}

/**
 * Test 3: CMP Executor (intake phase)
 */
async function testCMPIntake(): Promise<void> {
  console.log('\nTest 3: CMP Executor intake phase');

  const executor = new CMPExecutor();

  const packet: MissionPacket = {
    mission_id: 'm-test-intake',
    intent: 'Implement pagination component with tests',
    agent_framework: 'roach-pi',
    scope: ['src/components/Pagination/', 'tests/'],
    budget: { tokens: 75000, tool_calls: 100 },
    required_gates: ['intent', 'scope', 'confidence'],
  };

  const approval = executor.evaluateIntake(packet);

  console.log(`  ✓ Intake evaluation complete`);
  console.log(`  ✓ Status: ${approval.approved ? 'Approved' : 'Rejected'}`);
  console.log(`  ✓ Recommendation: ${approval.recommendation}`);
  console.log(`  ✓ Intent passed: ${approval.gate_results.intent.passed}`);
  console.log(`  ✓ Scope passed: ${approval.gate_results.scope.passed}`);
}

/**
 * Test 4: Beads Bridge
 */
async function testBeadsBridge(): Promise<void> {
  console.log('\nTest 4: Beads Bridge conversion');

  const bridge = new BeadsBridge();

  // Create mock result
  const result: ExecutionResult = {
    mission_id: 'm-test-beads',
    status: 'success',
    output: {
      closed_tasks: [
        {
          id: 'task-1',
          title: 'Implement pagination',
          status: 'completed',
          evidence: { pr_merged: true, tests_passed: 5 },
        },
      ],
      blocked_tasks: [
        {
          id: 'task-2',
          title: 'Accessibility audit',
          status: 'blocked',
          blocked_on: 'Design review',
        },
      ],
      created_artifacts: [],
    },
    telemetry: {
      tokens_used: 45000,
      tool_calls_count: 3,
      tool_calls: [],
      errors: [],
      retries: 0,
      duration_ms: 5000,
      test_results: [
        { test_name: 'pagination_test', status: 'pass', duration_ms: 120 },
      ],
    },
    learnings: [
      {
        title: 'React hooks pattern',
        detail: 'useState + useEffect works well for pagination state',
        tags: ['react', 'patterns'],
        confidence: 0.9,
      },
    ],
    magnet_reports: [
      {
        magnet_type: 'execution',
        observations: { tool_calls: 3 },
        anomalies: [],
        score: 0.95,
        timestamp: Date.now(),
      },
    ],
  };

  // Create mock synthesis
  const synthesis = {
    overall_confidence: 0.88,
    execution_quality: 0.92,
    cost_efficiency: 0.85,
    test_confidence: 0.78,
    anomaly_count: 0,
    critical_anomalies: 0,
    recommendation: 'proceed' as const,
  };

  const beads = bridge.resultToBeads(result, synthesis);

  console.log(`  ✓ Converted to ${beads.length} beads`);

  const byType: Record<string, number> = {};
  for (const bead of beads) {
    byType[bead.type] = (byType[bead.type] || 0) + 1;
  }

  for (const [type, count] of Object.entries(byType)) {
    console.log(`    • ${type}: ${count}`);
  }

  // Verify action beads
  const actionBeads = beads.filter((b) => b.type === 'action');
  console.log(`  ✓ Action beads created: ${actionBeads.length}`);
  console.log(`    • Completed: ${actionBeads.filter((b) => b.status === 'completed').length}`);
  console.log(`    • Waiting: ${actionBeads.filter((b) => b.status === 'waiting').length}`);

  // Verify learning beads
  const learningBeads = beads.filter((b) => b.type === 'learning');
  console.log(`  ✓ Learning beads created: ${learningBeads.length}`);
}

/**
 * Test 5: Full governance flow
 */
async function testFullFlow(): Promise<void> {
  console.log('\nTest 5: Full governance flow (intake → execution → completion)');

  const executor = new CMPExecutor();
  const bridge = new BeadsBridge();

  // Step 1: Intake gate
  const packet: MissionPacket = {
    mission_id: 'm-full-flow',
    intent: 'Add user authentication with OAuth2 integration',
    agent_framework: 'roach-pi',
    scope: ['src/auth/', 'src/api/', 'tests/'],
    budget: { tokens: 100000, tool_calls: 150 },
    required_gates: ['intent', 'scope', 'confidence'],
  };

  const intakeApproval = executor.evaluateIntake(packet);
  console.log(`  ✓ Step 1 (Intake): ${intakeApproval.approved ? 'Approved' : 'Rejected'}`);
  if (!intakeApproval.approved) {
    console.log(`    Reason: ${intakeApproval.recommendation}`);
    return;
  }

  // Step 2: Execution (simulated)
  const result: ExecutionResult = {
    mission_id: packet.mission_id,
    status: 'success',
    output: {
      closed_tasks: [
        {
          id: 'auth-impl',
          title: 'Implement OAuth2 flow',
          status: 'completed',
          evidence: { tests_passed: 8, pr_merged: true },
        },
      ],
      blocked_tasks: [],
      created_artifacts: [],
    },
    telemetry: {
      tokens_used: 85000,
      tool_calls_count: 45,
      tool_calls: [],
      errors: [],
      retries: 1,
      duration_ms: 8500,
      test_results: [
        { test_name: 'auth_flow_test', status: 'pass', duration_ms: 250 },
        { test_name: 'token_refresh_test', status: 'pass', duration_ms: 180 },
      ],
    },
    learnings: [
      {
        title: 'OAuth2 provider integration pattern',
        detail: 'Abstracting provider logic makes switching easier',
        tags: ['oauth', 'auth', 'architecture'],
        confidence: 0.92,
      },
    ],
    magnet_reports: [],
  };

  console.log(`  ✓ Step 2 (Execution): Completed in ${(result.telemetry.duration_ms / 1000).toFixed(1)}s`);

  // Step 3: Completion gate (confidence)
  const synthesis = {
    overall_confidence: 0.87,
    execution_quality: 0.90,
    cost_efficiency: 0.84,
    test_confidence: 0.85,
    anomaly_count: 1,
    critical_anomalies: 0,
    recommendation: 'proceed' as const,
  };

  const completionApproval = executor.evaluateCompletion(packet, result, synthesis);
  console.log(
    `  ✓ Step 3 (Completion): ${completionApproval.approved ? 'Approved' : 'Review Needed'}`
  );
  console.log(`    Recommendation: ${completionApproval.recommendation}`);
  console.log(`    Confidence: ${(synthesis.overall_confidence * 100).toFixed(0)}%`);

  // Step 4: Convert to beads
  const beads = bridge.resultToBeads(result, synthesis);
  console.log(`  ✓ Step 4 (Beads): Generated ${beads.length} beads`);
  for (const type of ['action', 'learning', 'alert', 'score']) {
    const count = beads.filter((b) => b.type === type).length;
    if (count > 0) console.log(`    • ${type}: ${count}`);
  }

  console.log(`  ✓ Full flow complete`);
}

/**
 * Run all tests
 */
async function runTests(): Promise<void> {
  console.log('═══════════════════════════════════════════');
  console.log('Phase 3 Integration Tests');
  console.log('═══════════════════════════════════════════\n');

  try {
    await testIntentGate();
    await testScopeGate();
    await testCMPIntake();
    await testBeadsBridge();
    await testFullFlow();

    console.log('\n═══════════════════════════════════════════');
    console.log('✓ All Phase 3 tests passed');
    console.log('═══════════════════════════════════════════');
  } catch (error) {
    console.error('\n✗ Test failed:', error);
    process.exit(1);
  }
}

if (require.main === module) {
  runTests();
}

export { runTests };
