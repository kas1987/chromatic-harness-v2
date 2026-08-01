import { POST } from './route';
import { NextRequest } from 'next/server';
import fs from 'fs';
import path from 'path';

jest.mock('fs');

const mockLease = {
  lease_id: 'lease-release-1',
  owner_agent: 'agent-x',
  resources: ['queue:bead-001'],
  mode: 'exclusive',
  status: 'active',
  created_at: new Date(Date.now() - 300000).toISOString(),
  expires_at: new Date(Date.now() + 3600000).toISOString(),
  heartbeat_at: new Date().toISOString(),
};

describe('POST /api/claims/force-release', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('releases an active lease and writes released_at', async () => {
    const written: string[] = [];
    (fs.readFileSync as jest.Mock).mockReturnValue(JSON.stringify(mockLease));
    (fs.writeFileSync as jest.Mock).mockImplementation((_p: string, data: string) => {
      written.push(data);
    });
    (fs.existsSync as jest.Mock).mockReturnValue(true);

    const request = new NextRequest('http://localhost:3000/api/claims/force-release', {
      method: 'POST',
      body: JSON.stringify({ lease_id: 'lease-release-1' }),
    });
    const response = await POST(request);
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.status).toBe('released');
    expect(written.length).toBe(1);
    const saved = JSON.parse(written[0].trim());
    expect(saved.status).toBe('released');
    expect(saved.released_at).toBeDefined();
  });

  test('writes an empty file when all leases are released', async () => {
    const written: string[] = [];
    (fs.readFileSync as jest.Mock).mockReturnValue(JSON.stringify({ ...mockLease, status: 'released' }));
    (fs.writeFileSync as jest.Mock).mockImplementation((_p: string, data: string) => {
      written.push(data);
    });
    (fs.existsSync as jest.Mock).mockReturnValue(true);

    const request = new NextRequest('http://localhost:3000/api/claims/force-release', {
      method: 'POST',
      body: JSON.stringify({ lease_id: 'lease-release-1' }),
    });
    const response = await POST(request);
    const body = await response.json();

    expect(response.status).toBe(404);
    // The file should still be written (empty) so leases.jsonl is never absent.
    expect(written.length).toBe(1);
    expect(written[0]).toBe('');
  });

  test('skips malformed JSONL rows and still releases a valid lease', async () => {
    const written: string[] = [];
    (fs.readFileSync as jest.Mock).mockReturnValue(
      JSON.stringify(mockLease) + '\nnot valid json\n'
    );
    (fs.writeFileSync as jest.Mock).mockImplementation((_p: string, data: string) => {
      written.push(data);
    });
    (fs.existsSync as jest.Mock).mockReturnValue(true);

    const request = new NextRequest('http://localhost:3000/api/claims/force-release', {
      method: 'POST',
      body: JSON.stringify({ lease_id: 'lease-release-1' }),
    });
    const response = await POST(request);
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.status).toBe('released');
  });

  test('returns 400 when lease_id is missing', async () => {
    const request = new NextRequest('http://localhost:3000/api/claims/force-release', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    const response = await POST(request);
    const body = await response.json();

    expect(response.status).toBe(400);
    expect(body.error).toContain('lease_id required');
  });
});
