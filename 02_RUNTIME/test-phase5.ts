/**
 * Phase 5 Integration Test
 *
 * Verifies that:
 * - Agents register at L0
 * - Sandbox validator enforces level constraints
 * - Promotion scorer evaluates promotion readiness
 * - SandboxLab orchestrates promotion lifecycle
 * - L0-L5 progression works correctly
 */

import { SandboxLab } from './sandbox-lab/sandbox-lab';
import { SandboxValidator } from './sandbox-lab/sandbox-validator';
import { PromotionScorer } from './sandbox-lab/promotion-scorer';
import { AgentBehavior, AgentTrustProfile } from './sandbox-lab/sandbox-types';

/**
 * Test 1: Agent registration and L0 dry-run
 */
async function testAgentRegistration(): Promise<void> {
  console.log('Test 1: Agent registration and L0 dry-run');

  const lab = new SandboxLab();

  // Register new agent
  const profile = lab.registerAgent('agent-openhands-001');

  console.log(`  ✓ Agent registered at L${profile.current_level}`);
  console.log(`  ✓ Profile created with success_rate: ${(profile.success_rate * 100).toFixed(0)}%`);

  // L0: Agent reasons only, no tool calls
  const l0Behavior: AgentBehavior = {
    agent_id: 'agent-openhands-001',
    level: 0,
    execution_time_ms: 5000,
    tool_calls: 0, // L0: no tools allowed
    errors: 0,
    scope_violations: 0,
    test_pass_rate: 0.9,
    confidence_delta: 0.15,
    observations: {},
    passed: true,
  };

  const validator = new SandboxValidator();
  const validation = validator.validate(l0Behavior);

  console.log(`  ✓ L0 validation passed: ${validation.passed}`);
  console.log(`  ✓ Confidence: ${(validation.confidence_score * 100).toFixed(0)}%`);

  if (!validation.passed) {
    throw new Error('L0 validation should pass for tool_calls=0');
  }
}

/**
 * Test 2: L0 -> L1 Promotion
 */
async function testL0ToL1Promotion(): Promise<void> {
  console.log('\nTest 2: L0 -> L1 Promotion');

  const lab = new SandboxLab({ min_executions_per_level: 2 });
  lab.registerAgent('agent-l1-test');

  // Execute L0 twice successfully
  for (let i = 0; i < 2; i++) {
    const behavior: AgentBehavior = {
      agent_id: 'agent-l1-test',
      level: 0,
      execution_time_ms: 4000,
      tool_calls: 0,
      errors: 0,
      scope_violations: 0,
      test_pass_rate: 0.95,
      confidence_delta: 0.12,
      observations: {},
      passed: true,
    };

    lab.recordExecution('agent-l1-test', behavior);
  }

  const profile = lab.getProfile('agent-l1-test');
  console.log(`  ✓ Executions completed: ${profile!.successful_executions}`);

  // Promote to L1
  lab.promoteAgent('agent-l1-test', 1, 'Passed L0 threshold');

  const updatedProfile = lab.getProfile('agent-l1-test');
  console.log(`  ✓ Agent promoted to L${updatedProfile!.current_level}`);
  console.log(`  ✓ Promotion history: ${updatedProfile!.promotion_history.length} entries`);

  if (updatedProfile!.current_level !== 1) {
    throw new Error('Promotion to L1 failed');
  }
}

/**
 * Test 3: L1 Read-only validation
 */
async function testL1ReadOnly(): Promise<void> {
  console.log('\nTest 3: L1 Read-only validation');

  const validator = new SandboxValidator();

  // L1: Good - read only
  const goodL1: AgentBehavior = {
    agent_id: 'agent-read-only',
    level: 1,
    execution_time_ms: 8000,
    tool_calls: 15, // Exploring files
    errors: 0,
    scope_violations: 0,
    test_pass_rate: 0.9,
    confidence_delta: 0.1,
    observations: {},
    passed: true,
  };

  const goodValidation = validator.validate(goodL1);
  console.log(`  ✓ L1 read-only validation passed: ${goodValidation.passed}`);

  // L1: Bad - attempted write
  const badL1: AgentBehavior = {
    agent_id: 'agent-write-attempt',
    level: 1,
    execution_time_ms: 5000,
    tool_calls: 10,
    errors: 0,
    scope_violations: 0,
    test_pass_rate: 0.8,
    confidence_delta: 0.05,
    observations: {
      write_attempts: ['src/app.ts', 'src/config.ts'],
    },
    passed: false,
  };

  const badValidation = validator.validate(badL1);
  console.log(`  ✓ L1 write-attempt validation failed: ${!badValidation.passed}`);
  console.log(`    Violations: ${badValidation.violations.length}`);

  if (badValidation.passed) {
    throw new Error('L1 should reject write attempts');
  }
}

/**
 * Test 4: Promotion scoring
 */
async function testPromotionScoring(): Promise<void> {
  console.log('\nTest 4: Promotion scoring');

  const lab = new SandboxLab({ min_executions_per_level: 2 });
  lab.registerAgent('agent-scorer-test');

  // Record successful executions
  for (let i = 0; i < 3; i++) {
    const behavior: AgentBehavior = {
      agent_id: 'agent-scorer-test',
      level: 0,
      execution_time_ms: 4000,
      tool_calls: 0,
      errors: 0,
      scope_violations: 0,
      test_pass_rate: 0.95,
      confidence_delta: 0.15,
      observations: {},
      passed: true,
    };

    lab.recordExecution('agent-scorer-test', behavior);
  }

  const profile = lab.getProfile('agent-scorer-test')!;
  console.log(`  ✓ Agent has ${profile.successful_executions} successful executions`);
  console.log(`  ✓ Success rate: ${(profile.success_rate * 100).toFixed(0)}%`);
  console.log(`  ✓ Avg confidence: ${(profile.avg_confidence * 100).toFixed(0)}%`);

  // Score promotion
  const lastBehavior: AgentBehavior = {
    agent_id: 'agent-scorer-test',
    level: 0,
    execution_time_ms: 4000,
    tool_calls: 0,
    errors: 0,
    scope_violations: 0,
    test_pass_rate: 0.95,
    confidence_delta: 0.15,
    observations: {},
    passed: true,
  };

  const scorer = new PromotionScorer();
  const decision = scorer.scorePromotion(
    'agent-scorer-test',
    0,
    profile,
    lastBehavior
  );

  console.log(`  ✓ Promotion decision: ${decision.recommended_level}`);
  console.log(`  ✓ Ready to promote: ${decision.ready_to_promote}`);
  console.log(`  ✓ Confidence: ${(decision.confidence_score * 100).toFixed(0)}%`);
}

/**
 * Test 5: Violation detection and demotion
 */
async function testViolationDemotion(): Promise<void> {
  console.log('\nTest 5: Violation detection and demotion');

  const lab = new SandboxLab();

  // Register and promote to L2
  lab.registerAgent('agent-violation');
  lab.promoteAgent('agent-violation', 1, 'Test');
  lab.promoteAgent('agent-violation', 2, 'Test');

  let profile = lab.getProfile('agent-violation')!;
  console.log(`  ✓ Agent at L${profile.current_level}`);

  // Violation: L2 attempted merge
  const violatingBehavior: AgentBehavior = {
    agent_id: 'agent-violation',
    level: 2,
    execution_time_ms: 6000,
    tool_calls: 8,
    errors: 0,
    scope_violations: 0,
    test_pass_rate: 0.8,
    confidence_delta: 0.05,
    observations: {
      merge_attempts: ['main', 'develop'],
    },
    passed: false,
  };

  const result = lab.recordExecution('agent-violation', violatingBehavior);

  profile = lab.getProfile('agent-violation')!;
  console.log(`  ✓ Violation detected: ${!result.validation_passed}`);
  console.log(`  ✓ Agent demoted to L${profile.current_level}`);
  console.log(`  ✓ Violation recorded: ${profile.last_violation?.violation_type}`);

  if (profile.current_level !== 1) {
    throw new Error('Agent should be demoted from L2 to L1');
  }
}

/**
 * Test 6: Full promotion lifecycle
 */
async function testFullPromotionLifecycle(): Promise<void> {
  console.log('\nTest 6: Full promotion lifecycle (L0 -> L5)');

  const lab = new SandboxLab({ min_executions_per_level: 1, auto_promote: true });
  lab.registerAgent('agent-full-lifecycle');

  // Execute and auto-promote through levels
  for (let level = 0; level < 5; level++) {
    for (let i = 0; i < 2; i++) {
      const behavior: AgentBehavior = {
        agent_id: 'agent-full-lifecycle',
        level: level as any,
        execution_time_ms: 5000,
        tool_calls: level * 5, // More tools at higher levels
        errors: 0,
        scope_violations: 0,
        test_pass_rate: 0.9 + level * 0.01,
        confidence_delta: 0.1,
        observations: {},
        passed: true,
      };

      lab.recordExecution('agent-full-lifecycle', behavior);
    }

    const profile = lab.getProfile('agent-full-lifecycle')!;
    console.log(`  ✓ Level ${level} completed, next level: ${profile.current_level}`);
  }

  const finalProfile = lab.getProfile('agent-full-lifecycle')!;
  console.log(`  ✓ Final level: L${finalProfile.current_level}`);
  console.log(`  ✓ Success rate: ${(finalProfile.success_rate * 100).toFixed(0)}%`);
  console.log(`  ✓ Promotion history: ${finalProfile.promotion_history.length} milestones`);

  if (finalProfile.current_level !== 5) {
    throw new Error('Agent should reach L5');
  }
}

/**
 * Run all tests
 */
async function runTests(): Promise<void> {
  console.log('═══════════════════════════════════════════');
  console.log('Phase 5 Integration Tests');
  console.log('═══════════════════════════════════════════\n');

  try {
    await testAgentRegistration();
    await testL0ToL1Promotion();
    await testL1ReadOnly();
    await testPromotionScoring();
    await testViolationDemotion();
    await testFullPromotionLifecycle();

    console.log('\n═══════════════════════════════════════════');
    console.log('✓ All Phase 5 tests passed');
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
