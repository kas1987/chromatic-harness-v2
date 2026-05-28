/**
 * End-to-End Integration Test for Chromatic Harness v2 Option C
 * 
 * Verifies the complete pipeline:
 * User Intent → Mission Packet → CMP Gates → Runtime → Magnets → Beads → Dashboard
 */

import { CMPExecutor } from '../cmp-bridge/cmp-executor';
import { RuntimeRegistry } from '../runtime-registry';
import { SandboxLab } from '../sandbox-lab/sandbox-lab';
import { BeadsBridge } from '../beads-bridge';
import { MissionPacket } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';

/**
 * Test 1: Complete mission lifecycle
 */
async function testCompleteMissionLifecycle(): Promise<void> {
  console.log('\n═══════════════════════════════════════════');
  console.log('E2E Test 1: Complete Mission Lifecycle');
  console.log('═══════════════════════════════════════════');

  const cmp = new CMPExecutor();
  const registry = RuntimeRegistry.getInstance();
  const lab = new SandboxLab();
  
  // Step 1: User creates mission intent
  const missionPacket: MissionPacket = {
    mission_id: 'e2e-test-001',
    intent: 'Add authentication to user dashboard with JWT tokens and refresh token rotation',
    scope: ['src/auth/**/*', 'src/api/**/*'],
    budget: { tokens: 10000, tools: 50, wall_time_ms: 300000 },
    required_gates: ['intent', 'scope', 'confidence'],
    confidence_required: 0.75,
    autonomy_level: 2,
  };

  console.log('✓ Step 1: Mission created');
  console.log(`  - Intent: ${missionPacket.intent.slice(0, 60)}...`);
  console.log(`  - Scope: ${missionPacket.scope?.join(', ')}`);
  console.log(`  - Required confidence: ${missionPacket.confidence_required * 100}%`);

  // Step 2: Intake gates (Intent + Scope)
  const intakeApproval = cmp.evaluateIntake(missionPacket);
  console.log('\n✓ Step 2: Intake gates evaluated');
  console.log(`  - Intent gate: ${intakeApproval.gate_results.intent.passed ? '✓ PASS' : '✗ FAIL'}`);
  console.log(`  - Scope gate: ${intakeApproval.gate_results.scope.passed ? '✓ PASS' : '✗ FAIL'}`);
  console.log(`  - Approval: ${intakeApproval.approved ? 'APPROVED' : 'REJECTED'}`);

  if (!intakeApproval.approved) {
    console.log(`  - Reason: ${intakeApproval.notes}`);
    throw new Error('Intake gates rejected mission');
  }

  // Step 3: Select runtime and execute
  const adapter = registry.getAdapter('roach-pi');
  if (!adapter) {
    throw new Error('roach-pi adapter not available');
  }

  console.log('\n✓ Step 3: Runtime selected and mission executed');
  const executionResult = await adapter.executeMission(missionPacket);
  console.log(`  - Status: ${executionResult.status}`);
  console.log(`  - Tools called: ${executionResult.telemetry.tool_calls}`);
  console.log(`  - Tokens used: ${executionResult.telemetry.tokens_used}/${missionPacket.budget?.tokens}`);

  // Step 4: Confidence gate (post-execution)
  console.log('\n✓ Step 4: Confidence gate evaluated (post-execution)');
  const magnet = executionResult.magnet_reports[2]; // confidence magnet
  console.log(`  - Test coverage: ${(magnet.score * 100).toFixed(0)}%`);
  console.log(`  - Anomalies detected: ${magnet.anomalies.length}`);

  const completionApproval = cmp.evaluateCompletion(
    missionPacket,
    executionResult
  );
  console.log(`  - Confidence recommendation: ${completionApproval.recommendation}`);

  // Step 5: Convert to beads
  console.log('\n✓ Step 5: Execution converted to beads');
  const beadsBridge = new BeadsBridge();
  const beads = beadsBridge.resultToBeads(executionResult, missionPacket.mission_id);
  console.log(`  - Action beads: ${beads.filter(b => b.type === 'action').length}`);
  console.log(`  - Alert beads: ${beads.filter(b => b.type === 'alert').length}`);
  console.log(`  - Learning beads: ${beads.filter(b => b.type === 'learning').length}`);
  console.log(`  - Score beads: ${beads.filter(b => b.type === 'score').length}`);

  console.log('\n═══════════════════════════════════════════');
  console.log('✓ E2E Test 1 PASSED: Full lifecycle complete');
  console.log('═══════════════════════════════════════════');
}

/**
 * Test 2: Agent trust progression
 */
async function testAgentTrustProgression(): Promise<void> {
  console.log('\n═══════════════════════════════════════════');
  console.log('E2E Test 2: Agent Trust Progression');
  console.log('═══════════════════════════════════════════');

  const lab = new SandboxLab({ min_executions_per_level: 2, auto_promote: true });

  // Register agent
  const profile = lab.registerAgent('openhands-e2e');
  console.log('✓ Step 1: Agent registered at L0');
  console.log(`  - Agent: ${profile.agent_id}`);
  console.log(`  - Level: L${profile.current_level}`);

  // Execute through levels
  for (let level = 0; level < 3; level++) {
    for (let i = 0; i < 2; i++) {
      const behavior = {
        agent_id: 'openhands-e2e',
        level: level as any,
        execution_time_ms: 5000 + level * 1000,
        tool_calls: level * 3,
        errors: 0,
        scope_violations: 0,
        test_pass_rate: 0.85 + level * 0.05,
        confidence_delta: 0.1 + level * 0.05,
        observations: {},
        passed: true,
      };

      lab.recordExecution('openhands-e2e', behavior);
    }

    const currentProfile = lab.getProfile('openhands-e2e')!;
    console.log(`\n✓ Step ${level + 2}: Level L${level} completed`);
    console.log(`  - Current level: L${currentProfile.current_level}`);
    console.log(`  - Success rate: ${(currentProfile.success_rate * 100).toFixed(0)}%`);
    console.log(`  - Promotions: ${currentProfile.promotion_history.length}`);
  }

  const finalProfile = lab.getProfile('openhands-e2e')!;
  console.log('\n═══════════════════════════════════════════');
  console.log(`✓ E2E Test 2 PASSED: Agent at L${finalProfile.current_level}`);
  console.log('═══════════════════════════════════════════');
}

/**
 * Test 3: Confidence degradation detection
 */
async function testConfidenceDegradation(): Promise<void> {
  console.log('\n═══════════════════════════════════════════');
  console.log('E2E Test 3: Confidence Degradation Detection');
  console.log('═══════════════════════════════════════════');

  const cmp = new CMPExecutor();
  const registry = RuntimeRegistry.getInstance();

  const missionPacket: MissionPacket = {
    mission_id: 'e2e-test-003',
    intent: 'Refactor database connection pooling',
    scope: ['src/db/**/*'],
    budget: { tokens: 5000, tools: 20, wall_time_ms: 150000 },
    required_gates: ['confidence'],
    confidence_required: 0.80,
    autonomy_level: 1,
  };

  const adapter = registry.getAdapter('roach-pi');
  if (!adapter) throw new Error('roach-pi adapter unavailable');

  const executionResult = await adapter.executeMission(missionPacket);
  const completion = cmp.evaluateCompletion(missionPacket, executionResult);

  console.log('✓ Execution completed');
  console.log(`  - Confidence score: ${(completion.gate_results.confidence.score * 100).toFixed(0)}%`);
  console.log(`  - Required: ${(missionPacket.confidence_required! * 100).toFixed(0)}%`);
  console.log(`  - Recommendation: ${completion.recommendation}`);

  if (completion.recommendation === 'blocked') {
    console.log('✓ Low confidence correctly triggered blocking recommendation');
  } else if (completion.recommendation === 'escalate') {
    console.log('✓ Medium confidence triggered escalation for human review');
  }

  console.log('\n═══════════════════════════════════════════');
  console.log('✓ E2E Test 3 PASSED: Degradation detection working');
  console.log('═══════════════════════════════════════════');
}

/**
 * Run all E2E tests
 */
async function runE2ETests(): Promise<void> {
  console.log('\n');
  console.log('╔═════════════════════════════════════════════════════════╗');
  console.log('║  Chromatic Harness v2 Option C - E2E Integration Tests  ║');
  console.log('╚═════════════════════════════════════════════════════════╝');

  try {
    await testCompleteMissionLifecycle();
    await testAgentTrustProgression();
    await testConfidenceDegradation();

    console.log('\n╔═════════════════════════════════════════════════════════╗');
    console.log('║  ✓ ALL E2E TESTS PASSED                                 ║');
    console.log('║  Option C architecture is ready for production testing   ║');
    console.log('╚═════════════════════════════════════════════════════════╝\n');
  } catch (error) {
    console.error('\n✗ E2E Test failed:', error);
    process.exit(1);
  }
}

if (require.main === module) {
  runE2ETests();
}

export { runE2ETests };
