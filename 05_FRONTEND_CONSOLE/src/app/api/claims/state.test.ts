import { GET } from './state/route';
import { NextRequest } from 'next/server';
import fs from 'fs';
import path from 'path';

// Mock fs module
jest.mock('fs');

const mockLeaseData = [
  {
    lease_id: 'lease-001',
    owner_agent: 'agent-a',
    resources: ['queue:bead-001'],
    mode: 'exclusive',
    status: 'active',
    created_at: new Date(Date.now() - 300000).toISOString(),
    expires_at: new Date(Date.now() + 3600000).toISOString(),
    heartbeat_at: new Date().toISOString(),
    metadata: { kind: 'queue_claim' },
  },
  {
    lease_id: 'lease-002',
    owner_agent: 'agent-b',
    resources: ['queue:bead-001'], // Conflict with lease-001
    mode: 'exclusive',
    status: 'active',
    created_at: new Date(Date.now() - 200000).toISOString(),
    expires_at: new Date(Date.now() + 3600000).toISOString(),
    heartbeat_at: new Date().toISOString(),
    metadata: { kind: 'queue_claim' },
  },
  {
    lease_id: 'lease-stale',
    owner_agent: 'agent-crashed',
    resources: ['queue:bead-002'],
    mode: 'exclusive',
    status: 'active',
    created_at: new Date(Date.now() - 7200000).toISOString(),
    expires_at: new Date(Date.now() - 100000).toISOString(), // Expired
    heartbeat_at: new Date(Date.now() - 7200000).toISOString(),
    metadata: { kind: 'queue_claim' },
  },
];

describe('GET /api/claims/state', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('returns active claims and conflicts', async () => {
    (fs.readFileSync as jest.Mock).mockReturnValue(
      mockLeaseData.map((l) => JSON.stringify(l)).join('\n')
    );

    const request = new NextRequest('http://localhost:3000/api/claims/state');
    const response = await GET();

    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.active_claims).toHaveLength(2);
    expect(body.stale_claims).toContain('lease-stale');
    expect(body.conflicts).toHaveLength(1);
    expect(body.conflicts[0]).toEqual(
      expect.objectContaining({
        lease_a: 'lease-001',
        lease_b: 'lease-002',
        resource: 'queue:bead-001',
        owner_a: 'agent-a',
        owner_b: 'agent-b',
      })
    );
  });

  test('detects stale claims (expired)', async () => {
    (fs.readFileSync as jest.Mock).mockReturnValue(
      mockLeaseData.map((l) => JSON.stringify(l)).join('\n')
    );

    const request = new NextRequest('http://localhost:3000/api/claims/state');
    const response = await GET();

    const body = await response.json();

    expect(body.stale_claims).toContain('lease-stale');
    expect(body.active_claims).not.toContainEqual(
      expect.objectContaining({ lease_id: 'lease-stale' })
    );
  });

  test('detects multiple conflicts', async () => {
    const complexLeaseData = [
      {
        lease_id: 'lease-x',
        owner_agent: 'agent-x',
        resources: ['queue:bead-a', 'queue:bead-b'],
        mode: 'exclusive',
        status: 'active',
        created_at: new Date(Date.now() - 300000).toISOString(),
        expires_at: new Date(Date.now() + 3600000).toISOString(),
        heartbeat_at: new Date().toISOString(),
        metadata: {},
      },
      {
        lease_id: 'lease-y',
        owner_agent: 'agent-y',
        resources: ['queue:bead-b', 'queue:bead-c'],
        mode: 'exclusive',
        status: 'active',
        created_at: new Date(Date.now() - 200000).toISOString(),
        expires_at: new Date(Date.now() + 3600000).toISOString(),
        heartbeat_at: new Date().toISOString(),
        metadata: {},
      },
      {
        lease_id: 'lease-z',
        owner_agent: 'agent-z',
        resources: ['queue:bead-c'],
        mode: 'exclusive',
        status: 'active',
        created_at: new Date(Date.now() - 100000).toISOString(),
        expires_at: new Date(Date.now() + 3600000).toISOString(),
        heartbeat_at: new Date().toISOString(),
        metadata: {},
      },
    ];

    (fs.readFileSync as jest.Mock).mockReturnValue(
      complexLeaseData.map((l) => JSON.stringify(l)).join('\n')
    );

    const request = new NextRequest('http://localhost:3000/api/claims/state');
    const response = await GET();

    const body = await response.json();

    // lease-x and lease-y conflict on bead-b, lease-y and lease-z conflict on bead-c
    expect(body.conflicts.length).toBeGreaterThanOrEqual(2);
  });

  test('ignores read-only locks for conflict detection', async () => {
    const readOnlyData = [
      {
        lease_id: 'lease-read-1',
        owner_agent: 'agent-reader-1',
        resources: ['queue:bead-shared'],
        mode: 'read',
        status: 'active',
        created_at: new Date(Date.now() - 300000).toISOString(),
        expires_at: new Date(Date.now() + 3600000).toISOString(),
        heartbeat_at: new Date().toISOString(),
        metadata: {},
      },
      {
        lease_id: 'lease-read-2',
        owner_agent: 'agent-reader-2',
        resources: ['queue:bead-shared'],
        mode: 'read',
        status: 'active',
        created_at: new Date(Date.now() - 200000).toISOString(),
        expires_at: new Date(Date.now() + 3600000).toISOString(),
        heartbeat_at: new Date().toISOString(),
        metadata: {},
      },
    ];

    (fs.readFileSync as jest.Mock).mockReturnValue(
      readOnlyData.map((l) => JSON.stringify(l)).join('\n')
    );

    const request = new NextRequest('http://localhost:3000/api/claims/state');
    const response = await GET();

    const body = await response.json();

    // Read-only locks should not create conflicts
    expect(body.conflicts).toHaveLength(0);
  });

  test('handles missing lease file gracefully', async () => {
    (fs.readFileSync as jest.Mock).mockImplementation(() => {
      throw new Error('ENOENT');
    });

    const request = new NextRequest('http://localhost:3000/api/claims/state');
    const response = await GET();

    const body = await response.json();

    expect(body.active_claims).toHaveLength(0);
    expect(body.stale_claims).toHaveLength(0);
    expect(body.conflicts).toHaveLength(0);
  });

  test('returns timestamp with response', async () => {
    (fs.readFileSync as jest.Mock).mockReturnValue('');

    const request = new NextRequest('http://localhost:3000/api/claims/state');
    const response = await GET();

    const body = await response.json();

    expect(body.timestamp).toBeDefined();
    expect(new Date(body.timestamp).getTime()).toBeGreaterThan(0);
  });

  test('detects resource path overlaps (hierarchical)', async () => {
    const hierarchicalData = [
      {
        lease_id: 'lease-parent',
        owner_agent: 'agent-parent',
        resources: ['files/path'],
        mode: 'exclusive',
        status: 'active',
        created_at: new Date(Date.now() - 300000).toISOString(),
        expires_at: new Date(Date.now() + 3600000).toISOString(),
        heartbeat_at: new Date().toISOString(),
        metadata: {},
      },
      {
        lease_id: 'lease-child',
        owner_agent: 'agent-child',
        resources: ['files/path/subdir'],
        mode: 'exclusive',
        status: 'active',
        created_at: new Date(Date.now() - 200000).toISOString(),
        expires_at: new Date(Date.now() + 3600000).toISOString(),
        heartbeat_at: new Date().toISOString(),
        metadata: {},
      },
    ];

    (fs.readFileSync as jest.Mock).mockReturnValue(
      hierarchicalData.map((l) => JSON.stringify(l)).join('\n')
    );

    const request = new NextRequest('http://localhost:3000/api/claims/state');
    const response = await GET();

    const body = await response.json();

    // Parent and child paths should conflict
    expect(body.conflicts).toHaveLength(1);
  });

  test('skips malformed JSONL rows without crashing', async () => {
    (fs.readFileSync as jest.Mock).mockReturnValue(
      '{"lease_id":"l1","owner_agent":"a","resources":[],"mode":"exclusive","status":"active","created_at":"2026-01-01T00:00:00Z","expires_at":"2099-01-01T00:00:00Z","heartbeat_at":"2026-01-01T00:00:00Z"}\n' +
      'this is not valid json\n'
    );

    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.active_claims).toHaveLength(1);
    expect(body.active_claims[0].lease_id).toBe('l1');
  });

  test('passes released_at through to active claims', async () => {
    const lease = {
      lease_id: 'lease-released',
      owner_agent: 'agent-r',
      resources: ['queue:bead-r'],
      mode: 'exclusive',
      status: 'active',
      created_at: new Date(Date.now() - 300000).toISOString(),
      expires_at: new Date(Date.now() + 3600000).toISOString(),
      heartbeat_at: new Date().toISOString(),
      released_at: '2026-06-21T12:00:00Z',
    };

    (fs.readFileSync as jest.Mock).mockReturnValue(JSON.stringify(lease));

    const response = await GET();
    const body = await response.json();

    expect(body.active_claims[0].released_at).toBe('2026-06-21T12:00:00Z');
  });

  test('ignores conflicts between leases owned by the same agent', async () => {
    const sameOwnerData = [
      {
        lease_id: 'lease-same-1',
        owner_agent: 'agent-shared',
        resources: ['queue:bead-shared'],
        mode: 'exclusive',
        status: 'active',
        created_at: new Date(Date.now() - 300000).toISOString(),
        expires_at: new Date(Date.now() + 3600000).toISOString(),
        heartbeat_at: new Date().toISOString(),
      },
      {
        lease_id: 'lease-same-2',
        owner_agent: 'agent-shared',
        resources: ['queue:bead-shared'],
        mode: 'exclusive',
        status: 'active',
        created_at: new Date(Date.now() - 200000).toISOString(),
        expires_at: new Date(Date.now() + 3600000).toISOString(),
        heartbeat_at: new Date().toISOString(),
      },
    ];

    (fs.readFileSync as jest.Mock).mockReturnValue(
      sameOwnerData.map((l) => JSON.stringify(l)).join('\n')
    );

    const response = await GET();
    const body = await response.json();

    expect(body.conflicts).toHaveLength(0);
  });
});
