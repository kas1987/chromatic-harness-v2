import { NextResponse, NextRequest } from 'next/server';
import fs from 'fs';
import path from 'path';

interface LeaseRecord {
  lease_id: string;
  owner_agent: string;
  resources: string[];
  mode: string;
  status: 'active' | 'released' | 'expired';
  created_at: string;
  expires_at: string;
  heartbeat_at: string;
  released_at?: string;
  metadata?: Record<string, any>;
}

const REPO_ROOT = process.env.REPO_ROOT || path.join(process.cwd(), '..');

function loadLeases(): LeaseRecord[] {
  const leasePath = path.join(
    REPO_ROOT,
    'state',
    'leases',
    'active_leases.jsonl'
  );
  try {
    const content = fs.readFileSync(leasePath, 'utf8');
    return content
      .split('\n')
      .filter((line) => line.trim())
      .map((line) => {
        try {
          return JSON.parse(line) as LeaseRecord;
        } catch {
          console.warn('Skipping malformed lease row:', line.slice(0, 200));
          return null;
        }
      })
      .filter((lease): lease is LeaseRecord => lease !== null);
  } catch {
    return [];
  }
}

function writeLeases(leases: LeaseRecord[]): void {
  const leasePath = path.join(
    REPO_ROOT,
    'state',
    'leases',
    'active_leases.jsonl'
  );
  const dir = path.dirname(leasePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const content = leases
    .map((lease) => JSON.stringify(lease, null, 0))
    .join('\n');
  fs.writeFileSync(leasePath, (leases.length > 0 ? content + '\n' : ''), 'utf8');
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json() as { lease_id?: string };
    const leaseId = body.lease_id;

    if (!leaseId) {
      return NextResponse.json(
        { status: 'error', error: 'lease_id required' },
        { status: 400 }
      );
    }

    const leases = loadLeases();
    let found = false;

    for (const lease of leases) {
      if (lease.lease_id === leaseId && lease.status === 'active') {
        lease.status = 'released';
        lease.released_at = new Date().toISOString();
        found = true;
        break;
      }
    }

    if (found) {
      writeLeases(leases);
      return NextResponse.json({
        status: 'released',
        lease_id: leaseId,
        timestamp: new Date().toISOString(),
      });
    } else {
      return NextResponse.json(
        { status: 'not_found', lease_id: leaseId },
        { status: 404 }
      );
    }
  } catch (error) {
    console.error('Error force-releasing claim:', error);
    return NextResponse.json(
      { status: 'error', error: String(error) },
      { status: 500 }
    );
  }
}
