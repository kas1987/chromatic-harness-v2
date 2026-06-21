import { NextResponse } from 'next/server';
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
  metadata?: Record<string, any>;
}

interface ConflictPair {
  lease_a: string;
  lease_b: string;
  resource: string;
  owner_a: string;
  owner_b: string;
}

interface DeadlockCycle {
  cycle: string[];
  resources: string[];
  suggested_release: string[];
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
      .map((line) => JSON.parse(line) as LeaseRecord);
  } catch {
    return [];
  }
}

function isActive(record: LeaseRecord): boolean {
  if (record.status !== 'active') return false;
  try {
    const expiry = new Date(record.expires_at);
    return expiry > new Date();
  } catch {
    return true;
  }
}

function resourcesOverlap(a: string[], b: string[]): string[] {
  const overlaps = [];
  for (const ra of a) {
    const normalized_a = ra.replace(/\/$/, '');
    for (const rb of b) {
      const normalized_b = rb.replace(/\/$/, '');
      if (
        normalized_a === normalized_b ||
        normalized_a.startsWith(normalized_b + '/') ||
        normalized_b.startsWith(normalized_a + '/')
      ) {
        overlaps.push(normalized_a);
      }
    }
  }
  return overlaps;
}

function buildConflictGraph(
  activeLeases: LeaseRecord[]
): { conflicts: ConflictPair[]; graph: Record<string, string[]> } {
  const conflicts: ConflictPair[] = [];
  const graph: Record<string, string[]> = {};

  // Initialize graph nodes
  for (const lease of activeLeases) {
    if (lease.mode !== 'read') {
      graph[lease.lease_id] = [];
    }
  }

  // Find conflicts (pairwise overlaps among write/exclusive leases)
  const writeLocks = activeLeases.filter((l) => l.mode !== 'read');
  for (let i = 0; i < writeLocks.length; i++) {
    for (let j = i + 1; j < writeLocks.length; j++) {
      const overlaps = resourcesOverlap(
        writeLocks[i].resources,
        writeLocks[j].resources
      );
      for (const resource of overlaps) {
        conflicts.push({
          lease_a: writeLocks[i].lease_id,
          lease_b: writeLocks[j].lease_id,
          resource,
          owner_a: writeLocks[i].owner_agent,
          owner_b: writeLocks[j].owner_agent,
        });

        // Build directed graph for cycle detection
        graph[writeLocks[i].lease_id].push(writeLocks[j].lease_id);
        graph[writeLocks[j].lease_id].push(writeLocks[i].lease_id);
      }
    }
  }

  return { conflicts, graph };
}

function detectDeadlockCycles(
  graph: Record<string, string[]>,
  leaseMap: Map<string, LeaseRecord>
): DeadlockCycle[] {
  const visited = new Set<string>();
  const cycles: DeadlockCycle[] = [];

  function dfs(
    node: string,
    path: string[],
    pathSet: Set<string>
  ): void {
    if (pathSet.has(node)) {
      // Found a cycle
      const cycleStart = path.indexOf(node);
      const cycle = path.slice(cycleStart).concat(node);
      if (cycle.length > 2) {
        const resources = new Set<string>();
        const cycleLeases = cycle.slice(0, -1); // Remove duplicate end node
        for (let i = 0; i < cycleLeases.length; i++) {
          const current = cycleLeases[i];
          const next = cycleLeases[(i + 1) % cycleLeases.length];
          const currLease = leaseMap.get(current);
          const nextLease = leaseMap.get(next);
          if (currLease && nextLease) {
            const overlaps = resourcesOverlap(
              currLease.resources,
              nextLease.resources
            );
            overlaps.forEach((r) => resources.add(r));
          }
        }

        cycles.push({
          cycle: cycleLeases,
          resources: Array.from(resources),
          suggested_release: cycleLeases,
        });
      }
      return;
    }

    if (visited.has(node)) return;
    visited.add(node);

    pathSet.add(node);
    for (const neighbor of graph[node] || []) {
      dfs(neighbor, [...path, node], pathSet);
    }
    pathSet.delete(node);
  }

  for (const node of Object.keys(graph)) {
    if (!visited.has(node)) {
      dfs(node, [], new Set());
    }
  }

  return cycles;
}

export async function GET() {
  try {
    const leases = loadLeases();
    const activeLeases = leases.filter(isActive);
    const staleLeasesIds = leases
      .filter((l) => l.status === 'active' && !isActive(l))
      .map((l) => l.lease_id);

    const { conflicts, graph } = buildConflictGraph(activeLeases);
    const leaseMap = new Map(activeLeases.map((l) => [l.lease_id, l]));
    const deadlockCycles = detectDeadlockCycles(graph, leaseMap);

    return NextResponse.json({
      active_claims: activeLeases.map((l) => ({
        lease_id: l.lease_id,
        owner_agent: l.owner_agent,
        resources: l.resources,
        created_at: l.created_at,
        expires_at: l.expires_at,
        heartbeat_at: l.heartbeat_at,
        status: l.status,
      })),
      stale_claims: staleLeasesIds,
      conflicts,
      deadlock_cycles: deadlockCycles,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Error loading claims state:', error);
    return NextResponse.json(
      {
        active_claims: [],
        stale_claims: [],
        conflicts: [],
        deadlock_cycles: [],
        timestamp: new Date().toISOString(),
        error: String(error),
      },
      { status: 500 }
    );
  }
}
