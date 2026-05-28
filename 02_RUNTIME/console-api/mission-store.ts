/**
 * Mission Store
 *
 * In-memory datastore for missions, gates, and beads.
 * Phase 4 uses memory; can be swapped for database in Phase 5.
 */

import { MissionPacket, ExecutionResult } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';
import { MissionApproval } from '../cmp-bridge/cmp-executor';
import { Bead } from '../beads-bridge';

export interface StoredMission {
  packet: MissionPacket;
  status: 'pending' | 'approved' | 'executing' | 'completed' | 'rejected';
  intake_approval?: MissionApproval;
  execution_result?: ExecutionResult;
  completion_approval?: MissionApproval;
  created_at: number;
  started_at?: number;
  completed_at?: number;
}

export class MissionStore {
  private missions: Map<string, StoredMission> = new Map();
  private beads: Map<string, Bead> = new Map();
  private beadIndex: Map<string, string[]> = new Map(); // mission_id -> bead_ids

  /**
   * Store a new mission
   */
  createMission(packet: MissionPacket): StoredMission {
    const mission: StoredMission = {
      packet,
      status: 'pending',
      created_at: Date.now(),
    };
    this.missions.set(packet.mission_id, mission);
    this.beadIndex.set(packet.mission_id, []);
    return mission;
  }

  /**
   * Get mission by ID
   */
  getMission(mission_id: string): StoredMission | undefined {
    return this.missions.get(mission_id);
  }

  /**
   * List all missions
   */
  listMissions(filter?: { status?: string; limit?: number; offset?: number }): StoredMission[] {
    let missions = Array.from(this.missions.values());

    if (filter?.status) {
      missions = missions.filter((m) => m.status === filter.status);
    }

    const limit = filter?.limit || 50;
    const offset = filter?.offset || 0;

    return missions.sort((a, b) => b.created_at - a.created_at).slice(offset, offset + limit);
  }

  /**
   * Update mission status
   */
  updateMissionStatus(mission_id: string, status: StoredMission['status']): void {
    const mission = this.missions.get(mission_id);
    if (mission) {
      mission.status = status;
      if (status === 'executing' && !mission.started_at) {
        mission.started_at = Date.now();
      }
      if (status === 'completed' && !mission.completed_at) {
        mission.completed_at = Date.now();
      }
    }
  }

  /**
   * Store intake approval
   */
  setIntakeApproval(mission_id: string, approval: MissionApproval): void {
    const mission = this.missions.get(mission_id);
    if (mission) {
      mission.intake_approval = approval;
      mission.status = approval.approved ? 'approved' : 'rejected';
    }
  }

  /**
   * Store execution result
   */
  setExecutionResult(mission_id: string, result: ExecutionResult): void {
    const mission = this.missions.get(mission_id);
    if (mission) {
      mission.execution_result = result;
      mission.status = 'completed';
    }
  }

  /**
   * Store completion approval
   */
  setCompletionApproval(mission_id: string, approval: MissionApproval): void {
    const mission = this.missions.get(mission_id);
    if (mission) {
      mission.completion_approval = approval;
    }
  }

  /**
   * Add bead(s) to a mission
   */
  addBeads(mission_id: string, beads: Bead[]): void {
    for (const bead of beads) {
      this.beads.set(bead.id, bead);
      const missionBeads = this.beadIndex.get(mission_id) || [];
      missionBeads.push(bead.id);
      this.beadIndex.set(mission_id, missionBeads);
    }
  }

  /**
   * Get bead by ID
   */
  getBead(bead_id: string): Bead | undefined {
    return this.beads.get(bead_id);
  }

  /**
   * Get all beads for a mission
   */
  getBeadsForMission(mission_id: string): Bead[] {
    const bead_ids = this.beadIndex.get(mission_id) || [];
    return bead_ids.map((id) => this.beads.get(id)).filter((b) => !!b) as Bead[];
  }

  /**
   * List all beads (with optional filters)
   */
  listBeads(filter?: {
    status?: string;
    type?: string;
    limit?: number;
    offset?: number;
  }): Bead[] {
    let beads = Array.from(this.beads.values());

    if (filter?.status) {
      beads = beads.filter((b) => b.status === filter.status);
    }
    if (filter?.type) {
      beads = beads.filter((b) => b.type === filter.type);
    }

    const limit = filter?.limit || 50;
    const offset = filter?.offset || 0;

    return beads.sort((a, b) => b.created_at - a.created_at).slice(offset, offset + limit);
  }

  /**
   * Update bead status
   */
  updateBeadStatus(bead_id: string, status: Bead['status']): void {
    const bead = this.beads.get(bead_id);
    if (bead) {
      bead.status = status;
    }
  }

  /**
   * Get mission summary (for dashboard)
   */
  getMissionSummary(mission_id: string): {
    mission: StoredMission | undefined;
    beads: Bead[];
    gate_status: Record<string, any>;
    completion_time?: number;
  } | null {
    const mission = this.missions.get(mission_id);
    if (!mission) return null;

    const beads = this.getBeadsForMission(mission_id);
    const completion_time = mission.completed_at
      ? mission.completed_at - (mission.started_at || mission.created_at)
      : undefined;

    return {
      mission,
      beads,
      gate_status: {
        intake: mission.intake_approval
          ? {
              passed: mission.intake_approval.approved,
              recommendation: mission.intake_approval.recommendation,
            }
          : null,
        completion: mission.completion_approval
          ? {
              passed: mission.completion_approval.approved,
              recommendation: mission.completion_approval.recommendation,
            }
          : null,
      },
      completion_time,
    };
  }

  /**
   * Get store statistics
   */
  getStats(): {
    total_missions: number;
    missions_by_status: Record<string, number>;
    total_beads: number;
    beads_by_type: Record<string, number>;
    beads_by_status: Record<string, number>;
  } {
    const missions_by_status: Record<string, number> = {};
    const beads_by_type: Record<string, number> = {};
    const beads_by_status: Record<string, number> = {};

    for (const mission of this.missions.values()) {
      missions_by_status[mission.status] = (missions_by_status[mission.status] || 0) + 1;
    }

    for (const bead of this.beads.values()) {
      beads_by_type[bead.type] = (beads_by_type[bead.type] || 0) + 1;
      beads_by_status[bead.status] = (beads_by_status[bead.status] || 0) + 1;
    }

    return {
      total_missions: this.missions.size,
      missions_by_status,
      total_beads: this.beads.size,
      beads_by_type,
      beads_by_status,
    };
  }

  /**
   * Clear all data (for testing)
   */
  clear(): void {
    this.missions.clear();
    this.beads.clear();
    this.beadIndex.clear();
  }
}
