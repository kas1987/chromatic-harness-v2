const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3030";

export interface MissionPacket {
  objective: string;
  scope?: string[];
  budget?: { tokens: number; tools: number; wall_time_ms: number };
  required_gates?: string[];
  stop_conditions?: string[];
  autonomy_level?: 0 | 1 | 2 | 3 | 4 | 5;
  confidence_required?: number;
}

export interface Mission {
  mission_id: string;
  objective: string;
  status: "pending" | "running" | "completed" | "failed";
  confidence_required: number;
  autonomy_level: number;
  magnets: string[];
  stop_conditions: string[];
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface MagnetEvent {
  event_id: string;
  mission_id: string;
  magnet_name: string;
  inflection_point: string;
  risk_delta: number;
  recommended_action: string;
  timestamp: string;
}

export interface GateResult {
  gate_name: string;
  passed: boolean;
  score: number;
  issues: string[];
  suggestions: string[];
}

export interface Bead {
  bead_id: string;
  mission_id?: string;
  type: "action" | "alert" | "learning" | "score";
  title: string;
  source: string;
  priority: "p0" | "p1" | "p2" | "p3";
  status: "pending" | "active" | "done";
  severity?: "critical" | "high" | "medium" | "low";
  created_at: string;
  updated_at: string;
}

export interface AgentProfile {
  agent_id: string;
  current_level: 0 | 1 | 2 | 3 | 4 | 5;
  total_executions: number;
  successful_executions: number;
  success_rate: number;
  avg_confidence: number;
  risk_score: number;
  promotion_history: Array<{ level: number; date: string; reason: string }>;
  last_violation?: { date: string; violation_type: string };
}

async function apiCall<T>(
  method: string,
  path: string,
  body?: any
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const opts: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "API error");
  }
  const data = await res.json();
  return data.data;
}

export async function getMissions(): Promise<Mission[]> {
  return apiCall("GET", "/missions");
}

export async function getMission(id: string): Promise<Mission> {
  return apiCall("GET", `/missions/${id}`);
}

export async function createMission(packet: MissionPacket): Promise<Mission> {
  return apiCall("POST", "/missions", {
    packet,
    scope: packet.scope || ["src/**/*"],
    required_gates: packet.required_gates || ["intent", "scope"],
  });
}

export async function getMissionGates(id: string): Promise<GateResult[]> {
  return apiCall("GET", `/missions/${id}/gates`);
}

export async function getMissionMagnets(
  id: string
): Promise<Record<string, any>> {
  return apiCall("GET", `/missions/${id}/magnets`);
}

export async function getBeads(): Promise<Bead[]> {
  return apiCall("GET", "/beads");
}

export async function getBead(id: string): Promise<Bead> {
  return apiCall("GET", `/beads/${id}`);
}

export async function updateBeadStatus(
  id: string,
  status: "pending" | "active" | "done"
): Promise<Bead> {
  return apiCall("PATCH", `/beads/${id}`, { status });
}

export async function getMissionEvents(
  missionId: string
): Promise<MagnetEvent[]> {
  try {
    const gates = await getMissionGates(missionId);
    const magnets = await getMissionMagnets(missionId);

    const events: MagnetEvent[] = [];
    let eventId = 0;

    if (magnets.reports) {
      for (const report of magnets.reports) {
        events.push({
          event_id: `evt-${++eventId}`,
          mission_id: missionId,
          magnet_name: report.magnet_type,
          inflection_point: report.inflection_point || "execution",
          risk_delta: report.anomalies?.length > 0 ? 0.15 : 0,
          recommended_action:
            report.anomalies?.length > 0 ? report.anomalies[0] : "proceed",
          timestamp: new Date().toISOString(),
        });
      }
    }

    return events;
  } catch {
    return [];
  }
}

export async function getAgents(): Promise<AgentProfile[]> {
  return apiCall("GET", "/agents");
}

export async function getAgent(id: string): Promise<AgentProfile> {
  return apiCall("GET", `/agents/${id}`);
}

export async function getHealthStatus(): Promise<{ status: string }> {
  try {
    return await apiCall("GET", "/health");
  } catch {
    return { status: "unavailable" };
  }
}

export interface PromotionRecord {
  level: number;
  date: string;
  reason: string;
}

export interface LevelThreshold {
  min_executions: number;
  min_success_rate: number;
  max_risk: number;
}

export async function registerAgent(payload: {
  agent_id: string;
  description?: string;
  initial_level?: number;
}): Promise<AgentProfile> {
  return apiCall("POST", "/agents", payload);
}

export async function promoteAgent(
  agentId: string,
  newLevel: number,
  reason: string
): Promise<AgentProfile> {
  return apiCall("POST", `/agents/${agentId}/promote`, {
    new_level: newLevel,
    reason,
  });
}

export async function getLevelThresholds(): Promise<
  Record<string, LevelThreshold>
> {
  return apiCall("GET", "/agents/meta/level-thresholds");
}
