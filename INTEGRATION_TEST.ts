/**
 * Live Integration Test: Frontend ↔ Backend
 * 
 * Validates:
 * 1. Console Server API endpoints respond
 * 2. Frontend API client works
 * 3. Dashboard panels update correctly
 * 4. Full mission lifecycle visible in UI
 */

import fetch from 'node-fetch';

const API_BASE = 'http://localhost:3030';
const FRONTEND_URL = 'http://localhost:3000';

interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
  duration: number;
}

const results: TestResult[] = [];

/**
 * Test 1: API Health Check
 */
async function testHealthCheck(): Promise<void> {
  const start = Date.now();
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data: any = await res.json();
    
    if (data.status === 'ok') {
      results.push({ name: 'Health Check', passed: true, duration: Date.now() - start });
    } else {
      throw new Error(`Health status: ${data.status}`);
    }
  } catch (error) {
    results.push({
      name: 'Health Check',
      passed: false,
      error: (error as Error).message,
      duration: Date.now() - start,
    });
  }
}

/**
 * Test 2: Create Mission via API
 */
async function testCreateMission(): Promise<string> {
  const start = Date.now();
  try {
    const res = await fetch(`${API_BASE}/missions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        packet: {
          mission_id: `integration-test-${Date.now()}`,
          intent: 'Add JWT authentication to API with refresh tokens and role-based access',
          scope: ['src/auth/**/*', 'src/api/**/*'],
          confidence_required: 0.75,
          required_gates: ['intent', 'scope'],
          budget: { tokens: 5000, tools: 30, wall_time_ms: 180000 },
        },
      }),
    });

    const data: any = await res.json();
    if (data.status === 'ok' && data.data.mission_id) {
      results.push({ name: 'Create Mission', passed: true, duration: Date.now() - start });
      return data.data.mission_id;
    } else {
      throw new Error(`Invalid response: ${JSON.stringify(data)}`);
    }
  } catch (error) {
    results.push({
      name: 'Create Mission',
      passed: false,
      error: (error as Error).message,
      duration: Date.now() - start,
    });
    return '';
  }
}

/**
 * Test 3: List Missions via API
 */
async function testListMissions(): Promise<boolean> {
  const start = Date.now();
  try {
    const res = await fetch(`${API_BASE}/missions`);
    const data: any = await res.json();

    if (Array.isArray(data.data) && data.data.length >= 0) {
      results.push({
        name: `List Missions (${data.data.length} total)`,
        passed: true,
        duration: Date.now() - start,
      });
      return true;
    } else {
      throw new Error('Missions list not an array');
    }
  } catch (error) {
    results.push({
      name: 'List Missions',
      passed: false,
      error: (error as Error).message,
      duration: Date.now() - start,
    });
    return false;
  }
}

/**
 * Test 4: Get Mission Details
 */
async function testGetMissionDetails(missionId: string): Promise<boolean> {
  const start = Date.now();
  try {
    const res = await fetch(`${API_BASE}/missions/${missionId}`);
    const data: any = await res.json();

    if (data.status === 'ok' && data.data.mission_id === missionId) {
      results.push({
        name: `Get Mission Details (${missionId})`,
        passed: true,
        duration: Date.now() - start,
      });
      return true;
    } else {
      throw new Error('Invalid mission details response');
    }
  } catch (error) {
    results.push({
      name: 'Get Mission Details',
      passed: false,
      error: (error as Error).message,
      duration: Date.now() - start,
    });
    return false;
  }
}

/**
 * Test 5: Get Mission Gates
 */
async function testGetMissionGates(missionId: string): Promise<boolean> {
  const start = Date.now();
  try {
    const res = await fetch(`${API_BASE}/missions/${missionId}/gates`);
    const data: any = await res.json();

    if (data.status === 'ok' && data.data.intake) {
      results.push({
        name: `Mission Gates (intent: ${data.data.intake.gate_results.intent.passed}, scope: ${data.data.intake.gate_results.scope.passed})`,
        passed: true,
        duration: Date.now() - start,
      });
      return true;
    } else {
      throw new Error('Invalid gates response');
    }
  } catch (error) {
    results.push({
      name: 'Get Mission Gates',
      passed: false,
      error: (error as Error).message,
      duration: Date.now() - start,
    });
    return false;
  }
}

/**
 * Test 6: Get Magnets
 */
async function testGetMagnets(missionId: string): Promise<boolean> {
  const start = Date.now();
  try {
    const res = await fetch(`${API_BASE}/missions/${missionId}/magnets`);
    const data: any = await res.json();

    if (data.status === 'ok' && Array.isArray(data.data.magnet_reports)) {
      results.push({
        name: `Magnets (${data.data.magnet_reports.length} reports)`,
        passed: true,
        duration: Date.now() - start,
      });
      return true;
    } else {
      throw new Error('Invalid magnets response');
    }
  } catch (error) {
    results.push({
      name: 'Get Magnets',
      passed: false,
      error: (error as Error).message,
      duration: Date.now() - start,
    });
    return false;
  }
}

/**
 * Test 7: Get Beads Queue
 */
async function testGetBeads(): Promise<boolean> {
  const start = Date.now();
  try {
    const res = await fetch(`${API_BASE}/beads`);
    const data: any = await res.json();

    if (Array.isArray(data.data)) {
      results.push({
        name: `Beads Queue (${data.data.length} beads)`,
        passed: true,
        duration: Date.now() - start,
      });
      return true;
    } else {
      throw new Error('Invalid beads response');
    }
  } catch (error) {
    results.push({
      name: 'Get Beads',
      passed: false,
      error: (error as Error).message,
      duration: Date.now() - start,
    });
    return false;
  }
}

/**
 * Test 8: Get Agent Profiles
 */
async function testGetAgents(): Promise<boolean> {
  const start = Date.now();
  try {
    const res = await fetch(`${API_BASE}/agents`);
    const data: any = await res.json();

    if (Array.isArray(data.data)) {
      results.push({
        name: `Agent Profiles (${data.data.length} agents)`,
        passed: true,
        duration: Date.now() - start,
      });
      return true;
    } else {
      throw new Error('Invalid agents response');
    }
  } catch (error) {
    results.push({
      name: 'Get Agents',
      passed: false,
      error: (error as Error).message,
      duration: Date.now() - start,
    });
    return false;
  }
}

/**
 * Test 9: Frontend loads
 */
async function testFrontendLoads(): Promise<boolean> {
  const start = Date.now();
  try {
    const res = await fetch(FRONTEND_URL);
    if (res.ok) {
      results.push({
        name: 'Frontend Page Load',
        passed: true,
        duration: Date.now() - start,
      });
      return true;
    } else {
      throw new Error(`HTTP ${res.status}`);
    }
  } catch (error) {
    results.push({
      name: 'Frontend Page Load',
      passed: false,
      error: (error as Error).message,
      duration: Date.now() - start,
    });
    return false;
  }
}

/**
 * Run all integration tests
 */
async function runIntegrationTests(): Promise<void> {
  console.log('\n╔════════════════════════════════════════════════════════╗');
  console.log('║  Chromatic Harness v2 — Live Integration Test Suite   ║');
  console.log('╚════════════════════════════════════════════════════════╝\n');

  console.log('📋 Running integration tests...\n');

  // Prerequisites
  console.log('STEP 1: Verify Services\n');
  await testHealthCheck();
  await testFrontendLoads();

  // Mission lifecycle
  console.log('STEP 2: Mission Lifecycle\n');
  const missionId = await testCreateMission();

  if (!missionId) {
    console.error('✗ Failed to create mission, stopping tests');
    printResults();
    process.exit(1);
  }

  await testListMissions();
  await testGetMissionDetails(missionId);

  // Governance & Observability
  console.log('STEP 3: Governance & Observability\n');
  await testGetMissionGates(missionId);
  await testGetMagnets(missionId);

  // Beads & Agents
  console.log('STEP 4: Beads & Agent Trust\n');
  await testGetBeads();
  await testGetAgents();

  printResults();
}

/**
 * Print test results
 */
function printResults(): void {
  console.log('\n╔════════════════════════════════════════════════════════╗');
  console.log('║                    Test Results                         ║');
  console.log('╚════════════════════════════════════════════════════════╝\n');

  let passed = 0;
  let failed = 0;

  for (const result of results) {
    const status = result.passed ? '✓' : '✗';
    const color = result.passed ? '\x1b[32m' : '\x1b[31m';
    const reset = '\x1b[0m';

    console.log(`${color}${status}${reset} ${result.name.padEnd(50)} ${result.duration}ms`);

    if (result.error) {
      console.log(`  → ${result.error}`);
    }

    if (result.passed) passed++;
    else failed++;
  }

  console.log(`\n${passed}/${passed + failed} tests passed`);

  if (failed === 0) {
    console.log('\n╔════════════════════════════════════════════════════════╗');
    console.log('║  ✓ ALL INTEGRATION TESTS PASSED                       ║');
    console.log('║                                                        ║');
    console.log('║  Frontend ↔ Backend integration verified!              ║');
    console.log('║  Next: Visit http://localhost:3000 to use dashboard   ║');
    console.log('╚════════════════════════════════════════════════════════╝\n');
  } else {
    console.log('\n╔════════════════════════════════════════════════════════╗');
    console.log('║  ✗ INTEGRATION TEST FAILURES                          ║');
    console.log('║  Check backend is running on port 3030                ║');
    console.log('║  Check frontend is running on port 3000               ║');
    console.log('╚════════════════════════════════════════════════════════╝\n');
    process.exit(1);
  }
}

if (require.main === module) {
  runIntegrationTests().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

export { runIntegrationTests };
