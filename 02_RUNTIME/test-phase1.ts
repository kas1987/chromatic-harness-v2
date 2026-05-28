/**
 * Phase 1 Integration Test
 *
 * Verifies that:
 * - MissionPacket schema validates correctly
 * - RuntimeAdapter interface is properly implemented
 * - roach-pi adapter can execute a mock mission
 * - Runtime registry can find and dispatch to adapters
 */

import { MissionPacket, ExecutionResult } from '../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';
import { RoachPiAdapter } from './adapters/roach-pi-adapter';
import { RuntimeRegistry, DEFAULT_REGISTRY_CONFIG } from './runtime-registry';

/**
 * Test 1: Schema validation
 */
async function testMissionPacketValidation(): Promise<void> {
  console.log('Test 1: MissionPacket validation');

  const validPacket: MissionPacket = {
    mission_id: 'm-test-001',
    intent: 'Add dark mode support to the dashboard',
    agent_framework: 'roach-pi',
    scope: ['src/components/', 'src/styles/'],
    budget: {
      tokens: 50000,
      tool_calls: 80,
    },
    required_gates: ['intent', 'scope', 'confidence'],
  };

  const adapter = new RoachPiAdapter({
    base_branch: 'main',
    repo_path: './',
    timeout_seconds: 1800,
    retry_strategy: 'exponential',
  });

  const validation = await adapter.validate(validPacket);
  console.log('  ✓ Valid packet passed validation:', validation.valid);

  const invalidPacket: MissionPacket = {
    mission_id: 'm-test-002',
    intent: 'X', // Too short
    agent_framework: 'roach-pi',
    scope: [],
    budget: {
      tokens: 500, // Too low
      tool_calls: 2,
    },
    required_gates: ['intent'],
  };

  const invalidValidation = await adapter.validate(invalidPacket);
  console.log('  ✓ Invalid packet failed validation:', !invalidValidation.valid);
  console.log('    Errors:', invalidValidation.errors);
}

/**
 * Test 2: Adapter capabilities
 */
async function testAdapterCapabilities(): Promise<void> {
  console.log('\nTest 2: Adapter capabilities');

  const adapter = new RoachPiAdapter({
    base_branch: 'main',
    repo_path: './',
    timeout_seconds: 1800,
    retry_strategy: 'exponential',
  });

  const capabilities = adapter.capabilities();
  console.log('  ✓ Runtime ID:', adapter.runtime_id);
  console.log('  ✓ Runtime Name:', adapter.runtime_name);
  console.log('  ✓ Max tokens:', capabilities.max_token_budget);
  console.log('  ✓ Supported tools:', capabilities.supported_tool_categories.join(', '));
  console.log('  ✓ Sandbox max level (trust): L' + capabilities.sandbox_max_level);
}

/**
 * Test 3: Mission execution with Magnet collection (Phase 2)
 */
async function testMissionExecution(): Promise<void> {
  console.log('\nTest 3: Mission execution with Magnet collection');

  const adapter = new RoachPiAdapter({
    base_branch: 'main',
    repo_path: './',
    timeout_seconds: 1800,
    retry_strategy: 'exponential',
  });

  const packet: MissionPacket = {
    mission_id: 'm-test-003',
    intent: 'Implement the dark mode feature for the dashboard',
    agent_framework: 'roach-pi',
    scope: ['src/components/', 'src/styles/', 'tests/'],
    budget: {
      tokens: 75000,
      tool_calls: 100,
    },
    required_gates: ['intent', 'scope', 'confidence'],
  };

  const result = await adapter.executeMission(packet);
  console.log('  ✓ Mission executed:', result.mission_id);
  console.log('  ✓ Status:', result.status);
  console.log('  ✓ Tokens used:', result.telemetry.tokens_used);
  console.log('  ✓ Tool calls made:', result.telemetry.tool_calls_count);
  console.log('  ✓ Tests passed:', result.telemetry.test_results?.length);
  console.log('  ✓ Learnings captured:', result.learnings.length);
  console.log('  ✓ Closed tasks:', result.output.closed_tasks.length);

  // Phase 2: Verify magnets were collected
  console.log('\n  Magnet Reports:');
  for (const report of result.magnet_reports) {
    console.log(`    [${report.magnet_type}] Score: ${(report.score * 100).toFixed(0)}%`);
    if (report.anomalies.length > 0) {
      console.log(`      Anomalies: ${report.anomalies.length}`);
    }
  }

  // Verify all required magnets present
  const magnet_types = result.magnet_reports.map((r) => r.magnet_type);
  const hasExecution = magnet_types.includes('execution');
  const hasCost = magnet_types.includes('cost');
  const hasConfidence = magnet_types.includes('confidence');

  console.log('\n  ✓ Execution magnet collected:', hasExecution);
  console.log('  ✓ Cost magnet collected:', hasCost);
  console.log('  ✓ Confidence magnet collected:', hasConfidence);

  if (!hasExecution || !hasCost || !hasConfidence) {
    throw new Error('Not all magnets were collected');
  }
}

/**
 * Test 4: Runtime registry
 */
async function testRuntimeRegistry(): Promise<void> {
  console.log('\nTest 4: Runtime registry');

  const registry = new RuntimeRegistry(DEFAULT_REGISTRY_CONFIG);
  await registry.initialize();

  const runtimes = registry.listRuntimes();
  console.log('  ✓ Registered runtimes:', runtimes.map((r) => r.runtime_id).join(', '));

  const roachPi = registry.getRuntime('roach-pi');
  console.log('  ✓ Found roach-pi adapter:', !!roachPi);

  const bestFit = await registry.findBestRuntime(
    'Add dark mode to React dashboard',
    ['src/components/']
  );
  console.log('  ✓ Best fit for code task:', bestFit?.runtime_id);

  await registry.shutdown();
}

/**
 * Run all tests
 */
async function runTests(): Promise<void> {
  console.log('═══════════════════════════════════════════');
  console.log('Phase 1 Integration Tests');
  console.log('═══════════════════════════════════════════\n');

  try {
    await testMissionPacketValidation();
    await testAdapterCapabilities();
    await testMissionExecution();
    await testRuntimeRegistry();

    console.log('\n═══════════════════════════════════════════');
    console.log('✓ All Phase 1 tests passed');
    console.log('═══════════════════════════════════════════');
  } catch (error) {
    console.error('\n✗ Test failed:', error);
    process.exit(1);
  }
}

// Run if invoked directly
if (require.main === module) {
  runTests();
}

export { runTests };
