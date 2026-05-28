const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";

export interface Mission {
  mission_id: string;
  objective: string;
  agent_role: string;
  autonomy_level: string;
  confidence_required: number;
  allowed_tools: string[];
  stop_conditions: string[];
  required_outputs: string[];
  status: string;
  magnets: string[];
}

export interface MagnetEvent {
  event_id: string;
  mission_id: string;
  magnet_name: string;
  inflection_point: string;
  observed_signal: Record<string, unknown>;
  risk_delta: number;
  confidence_delta: number;
  evidence: string[];
  recommended_action: string;
  timestamp: string;
}

export interface Bead {
  bead_id: string;
  title: string;
  objective: string;
  priority: string;
  status: string;
  source: string;
  mission_id: string | null;
  created_at: string;
}

export interface CreateMissionRequest {
  objective: string;
  required_outputs?: string[];
}

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const getMissions = (): Promise<Mission[]> =>
  apiFetch<Mission[]>("/missions").catch(() => []);

export const getMission = (id: string): Promise<Mission> =>
  apiFetch<Mission>(`/missions/${id}`);

export const createMission = (req: CreateMissionRequest): Promise<Mission> =>
  apiFetch<Mission>("/missions", { method: "POST", body: JSON.stringify(req) });

export const getMissionEvents = (id: string): Promise<MagnetEvent[]> =>
  apiFetch<MagnetEvent[]>(`/missions/${id}/events`).catch(() => []);

export const getBeads = (): Promise<Bead[]> =>
  apiFetch<Bead[]>("/beads").catch(() => []);

export const getHealth = (): Promise<{ status: string; version: string }> =>
  apiFetch("/health");
