/**
 * Console API Server
 *
 * Express.js REST API exposing:
 * - Mission CRUD and status polling
 * - Gate decision visibility
 * - Beads queue management
 *
 * In Phase 4, runs in-memory. Phase 5 adds WebSocket and DB.
 */

import { MissionPacket } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';
import { CMPExecutor } from '../cmp-bridge/cmp-executor';
import { MissionStore } from './mission-store';
import { MissionEventHub } from './event_store';

/**
 * Simple HTTP response wrapper
 */
export interface APIResponse<T = any> {
  status: 'ok' | 'error';
  data?: T;
  error?: string;
  timestamp: number;
}

/**
 * Request/Response handlers (no express dependency for Phase 4)
 */
export class ConsoleServer {
  private store: MissionStore;
  private cmp: CMPExecutor;
  private port: number = 3030;

  constructor() {
    this.store = new MissionStore();
    this.cmp = new CMPExecutor();
  }

  /**
   * POST /missions - Create and intake-gate a mission
   */
  handleCreateMission(packet: MissionPacket): APIResponse<{
    mission_id: string;
    status: string;
    approval: any;
  }> {
    try {
      // Create mission
      const mission = this.store.createMission(packet);

      // Run intake gates
      const approval = this.cmp.evaluateIntake(packet);
      this.store.setIntakeApproval(packet.mission_id, approval);

      return {
        status: 'ok',
        data: {
          mission_id: mission.packet.mission_id,
          status: mission.status,
          approval: {
            approved: approval.approved,
            recommendation: approval.recommendation,
            notes: approval.notes,
          },
        },
        timestamp: Date.now(),
      };
    } catch (error) {
      return {
        status: 'error',
        error: (error as Error).message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * GET /missions/:id - Get mission status
   */
  handleGetMission(mission_id: string): APIResponse<any> {
    try {
      const summary = this.store.getMissionSummary(mission_id);
      if (!summary) {
        return {
          status: 'error',
          error: `Mission ${mission_id} not found`,
          timestamp: Date.now(),
        };
      }

      return {
        status: 'ok',
        data: {
          mission_id: summary.mission.packet.mission_id,
          status: summary.mission.status,
          intent: summary.mission.packet.intent,
          scope: summary.mission.packet.scope,
          created_at: summary.mission.created_at,
          started_at: summary.mission.started_at,
          completed_at: summary.mission.completed_at,
          completion_time_ms: summary.completion_time,
          gates: summary.gate_status,
          beads_count: summary.beads.length,
          tokens_used: summary.mission.execution_result?.telemetry.tokens_used,
          test_results: summary.mission.execution_result?.telemetry.test_results?.length || 0,
        },
        timestamp: Date.now(),
      };
    } catch (error) {
      return {
        status: 'error',
        error: (error as Error).message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * GET /missions - List all missions
   */
  handleListMissions(filter?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): APIResponse<any[]> {
    try {
      const missions = this.store.listMissions(filter);
      return {
        status: 'ok',
        data: missions.map((m) => ({
          mission_id: m.packet.mission_id,
          intent: m.packet.intent,
          status: m.status,
          created_at: m.created_at,
          completed_at: m.completed_at,
        })),
        timestamp: Date.now(),
      };
    } catch (error) {
      return {
        status: 'error',
        error: (error as Error).message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * GET /missions/:id/gates - Get gate results
   */
  handleGetGates(mission_id: string): APIResponse<any> {
    try {
      const mission = this.store.getMission(mission_id);
      if (!mission) {
        return {
          status: 'error',
          error: `Mission ${mission_id} not found`,
          timestamp: Date.now(),
        };
      }

      return {
        status: 'ok',
        data: {
          mission_id,
          intake: mission.intake_approval
            ? {
                approved: mission.intake_approval.approved,
                recommendation: mission.intake_approval.recommendation,
                gate_results: {
                  intent: {
                    passed: mission.intake_approval.gate_results.intent.passed,
                    clarity_score: mission.intake_approval.gate_results.intent.clarity_score,
                  },
                  scope: {
                    passed: mission.intake_approval.gate_results.scope.passed,
                    coverage_score: mission.intake_approval.gate_results.scope.coverage_score,
                  },
                },
                notes: mission.intake_approval.notes,
              }
            : null,
          completion: mission.completion_approval
            ? {
                approved: mission.completion_approval.approved,
                recommendation: mission.completion_approval.recommendation,
                notes: mission.completion_approval.notes,
              }
            : null,
        },
        timestamp: Date.now(),
      };
    } catch (error) {
      return {
        status: 'error',
        error: (error as Error).message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * GET /missions/:id/magnets - Get magnet reports
   */
  handleGetMagnets(mission_id: string): APIResponse<any> {
    try {
      const mission = this.store.getMission(mission_id);
      if (!mission || !mission.execution_result) {
        return {
          status: 'error',
          error: `Mission ${mission_id} not found or not executed`,
          timestamp: Date.now(),
        };
      }

      const reports = mission.execution_result.magnet_reports;
      return {
        status: 'ok',
        data: {
          mission_id,
          magnet_reports: reports.map((r) => ({
            magnet_type: r.magnet_type,
            score: r.score,
            anomaly_count: r.anomalies.length,
            anomalies: r.anomalies.map((a) => ({
              level: a.level,
              message: a.message,
            })),
          })),
        },
        timestamp: Date.now(),
      };
    } catch (error) {
      return {
        status: 'error',
        error: (error as Error).message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * GET /beads - List beads
   */
  handleListBeads(filter?: {
    status?: string;
    type?: string;
    limit?: number;
    offset?: number;
  }): APIResponse<any[]> {
    try {
      const beads = this.store.listBeads(filter);
      return {
        status: 'ok',
        data: beads.map((b) => ({
          id: b.id,
          type: b.type,
          status: b.status,
          title: b.title,
          priority: b.priority,
          source_mission: b.source.mission_id,
          created_at: b.created_at,
        })),
        timestamp: Date.now(),
      };
    } catch (error) {
      return {
        status: 'error',
        error: (error as Error).message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * GET /beads/:id - Get bead details
   */
  handleGetBead(bead_id: string): APIResponse<any> {
    try {
      const bead = this.store.getBead(bead_id);
      if (!bead) {
        return {
          status: 'error',
          error: `Bead ${bead_id} not found`,
          timestamp: Date.now(),
        };
      }

      return {
        status: 'ok',
        data: {
          id: bead.id,
          type: bead.type,
          status: bead.status,
          title: bead.title,
          description: bead.description,
          priority: bead.priority,
          tags: bead.tags,
          source: bead.source,
          evidence: bead.evidence,
          created_at: bead.created_at,
        },
        timestamp: Date.now(),
      };
    } catch (error) {
      return {
        status: 'error',
        error: (error as Error).message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * PATCH /beads/:id - Update bead status
   */
  handleUpdateBead(bead_id: string, status: string): APIResponse<any> {
    try {
      const bead = this.store.getBead(bead_id);
      if (!bead) {
        return {
          status: 'error',
          error: `Bead ${bead_id} not found`,
          timestamp: Date.now(),
        };
      }

      const validStates = ['pending', 'in_progress', 'completed', 'waiting'];
      if (!validStates.includes(status)) {
        return {
          status: 'error',
          error: `Invalid status "${status}". Must be one of: ${validStates.join(', ')}`,
          timestamp: Date.now(),
        };
      }

      this.store.updateBeadStatus(bead_id, status as any);

      return {
        status: 'ok',
        data: {
          id: bead_id,
          status,
          updated_at: Date.now(),
        },
        timestamp: Date.now(),
      };
    } catch (error) {
      return {
        status: 'error',
        error: (error as Error).message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * GET /health - Health check
   */
  handleHealth(): APIResponse<any> {
    const stats = this.store.getStats();
    return {
      status: 'ok',
      data: {
        service: 'chromatic-console-api',
        uptime_ms: process.uptime() * 1000,
        store_stats: stats,
      },
      timestamp: Date.now(),
    };
  }

  /**
   * Get store reference (for testing)
   */
  getStore(): MissionStore {
    return this.store;
  }

  /**
   * GET /agents - List all agents (Phase 6)
   */
  handleListAgents(): APIResponse<any[]> {
    try {
      return {
        status: 'ok',
        data: [
          {
            agent_id: 'demo-agent-1',
            current_level: 2,
            total_executions: 15,
            successful_executions: 12,
            success_rate: 0.8,
            avg_confidence: 0.75,
            risk_score: 0.2,
            promotion_history: [
              { level: 0, date: new Date(Date.now() - 86400000 * 7).toISOString(), reason: 'Initial registration' },
              { level: 1, date: new Date(Date.now() - 86400000 * 5).toISOString(), reason: 'Passed L0 threshold' },
              { level: 2, date: new Date(Date.now() - 86400000 * 2).toISOString(), reason: 'Passed L1 threshold' },
            ],
          },
        ],
        timestamp: Date.now(),
      };
    } catch (error) {
      return {
        status: 'error',
        error: (error as Error).message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * GET /agents/:id - Get agent profile (Phase 6)
   */
  handleGetAgent(agent_id: string): APIResponse<any> {
    try {
      const agents = [
        {
          agent_id: 'demo-agent-1',
          current_level: 2,
          total_executions: 15,
          successful_executions: 12,
          success_rate: 0.8,
          avg_confidence: 0.75,
          risk_score: 0.2,
          promotion_history: [
            { level: 0, date: new Date(Date.now() - 86400000 * 7).toISOString(), reason: 'Initial registration' },
            { level: 1, date: new Date(Date.now() - 86400000 * 5).toISOString(), reason: 'Passed L0 threshold' },
            { level: 2, date: new Date(Date.now() - 86400000 * 2).toISOString(), reason: 'Passed L1 threshold' },
          ],
          last_violation: { date: new Date(Date.now() - 86400000).toISOString(), violation_type: 'scope_drift' },
        },
      ];

      const agent = agents.find(a => a.agent_id === agent_id);
      if (!agent) {
        return {
          status: 'error',
          error: `Agent ${agent_id} not found`,
          timestamp: Date.now(),
        };
      }

      return {
        status: 'ok',
        data: agent,
        timestamp: Date.now(),
      };
    } catch (error) {
      return {
        status: 'error',
        error: (error as Error).message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * GET /missions/:id/events/replay — persisted WebSocket event history
   */
  handleReplayEvents(mission_id: string, limit = 100): APIResponse<{ events: unknown[] }> {
    try {
      const events = MissionEventHub.getInstance().replay(mission_id, limit);
      return {
        status: 'ok',
        data: { events, count: events.length },
        timestamp: Date.now(),
      };
    } catch (error) {
      return {
        status: 'error',
        error: (error as Error).message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * POST /internal/events — ingest event (multi-instance fanout target)
   */
  handleIngestEvent(body: {
    mission_id: string;
    type: string;
    data?: Record<string, unknown>;
    timestamp?: number;
  }): APIResponse<{ published: boolean }> {
    try {
      if (!body.mission_id || !body.type) {
        return {
          status: 'error',
          error: 'mission_id and type required',
          timestamp: Date.now(),
        };
      }
      MissionEventHub.getInstance().publish(body.mission_id, {
        type: body.type as any,
        mission_id: body.mission_id,
        timestamp: body.timestamp || Date.now(),
        data: body.data || {},
      });
      return {
        status: 'ok',
        data: { published: true },
        timestamp: Date.now(),
      };
    } catch (error) {
      return {
        status: 'error',
        error: (error as Error).message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * Get CMP executor (for testing)
   */
  getCMP(): CMPExecutor {
    return this.cmp;
  }
}
