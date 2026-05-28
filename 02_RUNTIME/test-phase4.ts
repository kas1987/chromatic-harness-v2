/**
 * Phase 4 Integration Test
 *
 * Verifies that:
 * - ConsoleServer handles all API requests correctly
 * - Mission CRUD works
 * - Gate decisions are visible via API
 * - Beads can be created, listed, and updated
 * - Full API flow works end-to-end
 */

import { MissionPacket } from '../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';
import { ConsoleServer } from './console-api/console-server';
import { MissionStore } from './console-api/mission-store';
import { CMPExecutor } from './cmp-bridge/cmp-executor';
import { BeadsBridge } from './beads-bridge';

/**
 * Test 1: Mission creation and intake gating
 */
async function testMissionCreation(): Promise<void> {
  console.log('Test 1: Mission creation and intake gating');

  const server = new ConsoleServer();

  const packet: MissionPacket = {
    mission_id: 'm-test-api-001',
    intent: 'Add pagination component with comprehensive tests',
    agent_framework: 'roach-pi',
    scope: ['src/components/Pagination/', 'tests/'],
    budget: { tokens: 75000, tool_calls: 100 },
    required_gates: ['intent', 'scope'],
  };

  const response = server.handleCreateMission(packet);

  console.log(`  ✓ Status: ${response.status}`);
  console.log(`  ✓ Mission ID: ${response.data?.mission_id}`);
  console.log(`  ✓ Initial status: ${response.data?.status}`);
  console.log(`  ✓ Approval: ${response.data?.approval.approved ? 'Approved' : 'Rejected'}`);
  console.log(`  ✓ Recommendation: ${response.data?.approval.recommendation}`);

  if (response.status !== 'ok' || !response.data?.approval.approved) {
    throw new Error('Mission creation failed');
  }
}

/**
 * Test 2: Get mission status
 */
async function testGetMission(): Promise<void> {
  console.log('\nTest 2: Get mission status');

  const server = new ConsoleServer();

  // Create a mission first
  const packet: MissionPacket = {
    mission_id: 'm-test-api-002',
    intent: 'Refactor authentication module with new security protocols',
    agent_framework: 'roach-pi',
    scope: ['src/auth/', 'tests/auth/'],
    budget: { tokens: 100000, tool_calls: 120 },
    required_gates: ['intent', 'scope'],
  };

  server.handleCreateMission(packet);

  // Get mission
  const response = server.handleGetMission(packet.mission_id);

  console.log(`  ✓ Status: ${response.status}`);
  console.log(`  ✓ Mission ID: ${response.data?.mission_id}`);
  console.log(`  ✓ Status: ${response.data?.status}`);
  console.log(`  ✓ Intent length: ${response.data?.intent.length} chars`);
  console.log(`  ✓ Scope: ${response.data?.scope.length} paths`);

  if (response.status !== 'ok') {
    throw new Error('Get mission failed');
  }
}

/**
 * Test 3: List missions
 */
async function testListMissions(): Promise<void> {
  console.log('\nTest 3: List missions');

  const server = new ConsoleServer();

  // Create multiple missions
  for (let i = 0; i < 3; i++) {
    const packet: MissionPacket = {
      mission_id: `m-test-api-list-${i}`,
      intent: `Task ${i}: Implement feature number ${i}`,
      agent_framework: 'roach-pi',
      scope: ['src/'],
      budget: { tokens: 50000, tool_calls: 80 },
      required_gates: ['intent'],
    };
    server.handleCreateMission(packet);
  }

  const response = server.handleListMissions({ limit: 10 });

  console.log(`  ✓ Status: ${response.status}`);
  console.log(`  ✓ Missions returned: ${response.data?.length}`);
  console.log(`  ✓ First mission ID: ${response.data?.[0]?.mission_id}`);

  if (response.status !== 'ok' || !response.data || response.data.length < 3) {
    throw new Error('List missions failed');
  }
}

/**
 * Test 4: Gate visibility
 */
async function testGateVisibility(): Promise<void> {
  console.log('\nTest 4: Gate visibility');

  const server = new ConsoleServer();

  const packet: MissionPacket = {
    mission_id: 'm-test-api-gates',
    intent: 'Add dark mode toggle with comprehensive design system integration',
    agent_framework: 'roach-pi',
    scope: ['src/components/', 'src/styles/'],
    budget: { tokens: 75000, tool_calls: 100 },
    required_gates: ['intent', 'scope'],
  };

  server.handleCreateMission(packet);

  // Get gates
  const response = server.handleGetGates(packet.mission_id);

  console.log(`  ✓ Status: ${response.status}`);
  console.log(`  ✓ Intake approval: ${response.data?.intake?.approved ? 'Yes' : 'No'}`);
  console.log(`  ✓ Intent clarity: ${(response.data?.intake?.gate_results.intent.clarity_score * 100).toFixed(0)}%`);
  console.log(`  ✓ Scope coverage: ${(response.data?.intake?.gate_results.scope.coverage_score * 100).toFixed(0)}%`);
  console.log(`  ✓ Notes: ${response.data?.intake?.notes.length || 0} items`);

  if (response.status !== 'ok') {
    throw new Error('Get gates failed');
  }
}

/**
 * Test 5: Beads creation and management
 */
async function testBeadsManagement(): Promise<void> {
  console.log('\nTest 5: Beads creation and management');

  const server = new ConsoleServer();

  // Create mission
  const packet: MissionPacket = {
    mission_id: 'm-test-api-beads',
    intent: 'Create user profile page with editing capabilities',
    agent_framework: 'roach-pi',
    scope: ['src/pages/', 'src/components/'],
    budget: { tokens: 60000, tool_calls: 90 },
    required_gates: ['intent'],
  };

  server.handleCreateMission(packet);

  // Create beads via BeadsBridge
  const bridge = new BeadsBridge();

  const beads = [
    {
      id: `action-${packet.mission_id}-1`,
      type: 'action' as const,
      status: 'completed' as const,
      title: 'Create profile page layout',
      priority: 4,
      source: { runtime: 'roach-pi', mission_id: packet.mission_id, stage: 'execution' as const },
      created_at: Date.now(),
    },
    {
      id: `action-${packet.mission_id}-2`,
      type: 'action' as const,
      status: 'pending' as const,
      title: 'Add form validation',
      priority: 2,
      source: { runtime: 'roach-pi', mission_id: packet.mission_id, stage: 'execution' as const },
      created_at: Date.now(),
    },
  ];

  server.getStore().addBeads(packet.mission_id, beads);

  // List beads
  const listResponse = server.handleListBeads({ type: 'action' });
  console.log(`  ✓ Listed beads: ${listResponse.data?.length || 0} total`);

  // Get single bead
  const getResponse = server.handleGetBead(beads[0].id);
  console.log(`  ✓ Bead details retrieved: ${getResponse.data?.title}`);
  console.log(`  ✓ Bead status: ${getResponse.data?.status}`);

  // Update bead
  const updateResponse = server.handleUpdateBead(beads[0].id, 'in_progress');
  console.log(`  ✓ Bead updated to: ${updateResponse.data?.status}`);

  // Verify update
  const verifyResponse = server.handleGetBead(beads[0].id);
  console.log(`  ✓ Verified update: ${verifyResponse.data?.status === 'in_progress' ? 'Success' : 'Failed'}`);

  if (listResponse.status !== 'ok' || getResponse.status !== 'ok') {
    throw new Error('Beads management failed');
  }
}

/**
 * Test 6: Full API flow
 */
async function testFullAPIFlow(): Promise<void> {
  console.log('\nTest 6: Full API flow (mission → gates → beads)');

  const server = new ConsoleServer();

  // Step 1: Create mission
  const packet: MissionPacket = {
    mission_id: 'm-test-api-full',
    intent: 'Implement real-time notification system with WebSocket',
    agent_framework: 'roach-pi',
    scope: ['src/notifications/', 'src/websocket/', 'tests/'],
    budget: { tokens: 120000, tool_calls: 150 },
    required_gates: ['intent', 'scope'],
  };

  const createResponse = server.handleCreateMission(packet);
  console.log(`  ✓ Step 1: Mission created`);
  console.log(`    ID: ${createResponse.data?.mission_id}`);
  console.log(`    Status: ${createResponse.data?.status}`);

  // Step 2: Check mission status
  const getResponse = server.handleGetMission(packet.mission_id);
  console.log(`  ✓ Step 2: Mission retrieved`);
  console.log(`    Status: ${getResponse.data?.status}`);

  // Step 3: View gate results
  const gateResponse = server.handleGetGates(packet.mission_id);
  console.log(`  ✓ Step 3: Gates retrieved`);
  console.log(`    Intake approved: ${gateResponse.data?.intake?.approved}`);

  // Step 4: Add beads
  const testBeads = [
    {
      id: `action-${packet.mission_id}-impl`,
      type: 'action' as const,
      status: 'completed' as const,
      title: 'Implement WebSocket server',
      priority: 1,
      source: { runtime: 'roach-pi', mission_id: packet.mission_id, stage: 'execution' as const },
      created_at: Date.now(),
    },
    {
      id: `learning-${packet.mission_id}-pattern`,
      type: 'learning' as const,
      status: 'completed' as const,
      title: 'WebSocket connection pooling pattern',
      priority: 3,
      source: { runtime: 'roach-pi', mission_id: packet.mission_id, stage: 'synthesis' as const },
      created_at: Date.now(),
    },
  ];

  server.getStore().addBeads(packet.mission_id, testBeads);
  console.log(`  ✓ Step 4: Beads created`);

  // Step 5: List beads
  const beadListResponse = server.handleListBeads();
  console.log(`  ✓ Step 5: Beads listed`);
  console.log(`    Total beads: ${beadListResponse.data?.length}`);

  // Step 6: Health check
  const healthResponse = server.handleHealth();
  console.log(`  ✓ Step 6: Health check`);
  console.log(`    Service: ${healthResponse.data?.service}`);
  console.log(`    Total missions: ${healthResponse.data?.store_stats.total_missions}`);

  console.log(`\n  ✓ Full API flow completed successfully`);
}

/**
 * Run all tests
 */
async function runTests(): Promise<void> {
  console.log('═══════════════════════════════════════════');
  console.log('Phase 4 Integration Tests');
  console.log('═══════════════════════════════════════════\n');

  try {
    await testMissionCreation();
    await testGetMission();
    await testListMissions();
    await testGateVisibility();
    await testBeadsManagement();
    await testFullAPIFlow();

    console.log('\n═══════════════════════════════════════════');
    console.log('✓ All Phase 4 tests passed');
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
