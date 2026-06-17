"use client";

import React from "react";

interface Mission {
  mission_id: string;
  objective: string;
  status: "pending" | "running" | "completed" | "failed";
  confidence_score: number;
  autonomy_level: number;
  magnets: string[];
  stop_conditions: string[];
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface AgentProfile {
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

interface AgentActivityProps {
  agents: AgentProfile[];
  missions: Mission[];
}

const ROLES = [
  "Builder Agent",
  "Scout Agent",
  "Auditor Agent",
  "Scribe Agent",
  "Reviewer Agent",
  "Orchestrator",
];

function roleName(a: AgentProfile, i: number): string {
  const parts = a.agent_id.split("-");
  const word = parts.find((p) => p.length > 4 && isNaN(Number(p)));
  return word
    ? word.charAt(0).toUpperCase() + word.slice(1) + " Agent"
    : ROLES[i % ROLES.length];
}

const LEVEL_COLORS = [
  "#64748b",
  "#3b82f6",
  "#22c55e",
  "#f59e0b",
  "#8b5cf6",
  "#ef4444",
];

function agentStatus(
  a: AgentProfile,
  runningMission: Mission | undefined
): { label: string; dot: string } {
  if (
    runningMission &&
    runningMission.magnets.some((m) => m.includes(a.agent_id.slice(0, 6)))
  ) {
    return { label: "Executing", dot: "live" };
  }
  if (a.success_rate > 0.8) return { label: "Completed", dot: "blue" };
  if (a.total_executions > 0) return { label: "Testing", dot: "warn" };
  return { label: "Idle", dot: "idle" };
}

function formatTimestamp(a: AgentProfile): string {
  if (a.promotion_history && a.promotion_history.length > 0) {
    const latest = a.promotion_history[a.promotion_history.length - 1];
    const d = new Date(latest.date);
    if (!isNaN(d.getTime())) {
      const hh = String(d.getHours()).padStart(2, "0");
      const mm = String(d.getMinutes()).padStart(2, "0");
      const ss = String(d.getSeconds()).padStart(2, "0");
      return `${hh}:${mm}:${ss}`;
    }
  }
  return "12:04:00";
}

function dotClass(dot: string): string {
  if (dot === "live") return "cc-dot-live";
  if (dot === "warn") return "cc-dot-warn";
  if (dot === "blue") return "cc-dot-idle";
  return "cc-dot-idle";
}

function statusColor(dot: string): string {
  if (dot === "live") return "var(--color-success)";
  if (dot === "warn") return "var(--color-warning)";
  if (dot === "blue") return "var(--color-accent-400)";
  return "var(--color-text-muted)";
}

export default function AgentActivity({ agents, missions }: AgentActivityProps) {
  const runningMission = missions.find((m) => m.status === "running");

  const executingCount = agents.filter((a) => {
    const { dot } = agentStatus(a, runningMission);
    return dot === "live";
  }).length;

  const avgSuccess =
    agents.length > 0
      ? (
          (agents.reduce((sum, a) => sum + a.success_rate, 0) / agents.length) *
          100
        ).toFixed(0)
      : "0";

  return (
    <div className="cc-panel" style={{ display: "flex", flexDirection: "column" }}>
      <div className="cc-panel-title">AGENT ACTIVITY</div>

      {agents.length === 0 ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "24px 0",
            gap: 6,
          }}
        >
          <span style={{ fontSize: 20, opacity: 0.18 }}>🤖</span>
          <span
            style={{
              fontSize: 12,
              color: "var(--cc-muted)",
              opacity: 0.5,
            }}
          >
            No active agents
          </span>
        </div>
      ) : (
        <div
          className="cc-scrollable"
          style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1 }}
        >
          {agents.map((agent, i) => {
            const { label, dot } = agentStatus(agent, runningMission);
            const levelColor = LEVEL_COLORS[agent.current_level] ?? "#64748b";
            const name = roleName(agent, i);
            const ts = formatTimestamp(agent);

            return (
              <div
                key={agent.agent_id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "7px 8px",
                  borderRadius: 5,
                  cursor: "default",
                  transition: "background var(--duration-fast)",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLDivElement).style.background =
                    "rgba(255,255,255,0.03)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLDivElement).style.background =
                    "transparent";
                }}
              >
                {/* Status dot */}
                <span className={dotClass(dot)} />

                {/* Name */}
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: "var(--color-text-primary)",
                    flex: 1,
                    minWidth: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {name}
                </span>

                {/* Level badge */}
                <span
                  className="cc-tag"
                  style={{
                    fontSize: 9,
                    background: `${levelColor}26`,
                    color: levelColor,
                    border: `1px solid ${levelColor}40`,
                    padding: "1px 5px",
                    borderRadius: 3,
                    fontWeight: 700,
                    letterSpacing: "0.04em",
                    flexShrink: 0,
                  }}
                >
                  L{agent.current_level}
                </span>

                {/* Status label */}
                <span
                  style={{
                    fontSize: 10,
                    color: statusColor(dot),
                    flexShrink: 0,
                    minWidth: 56,
                    textAlign: "right",
                  }}
                >
                  {label}
                </span>

                {/* Success rate */}
                <span
                  style={{
                    fontSize: 10,
                    color: "var(--cc-muted)",
                    flexShrink: 0,
                    minWidth: 30,
                    textAlign: "right",
                  }}
                >
                  {(agent.success_rate * 100).toFixed(0)}%
                </span>

                {/* Timestamp */}
                <span
                  style={{
                    fontSize: 10,
                    fontFamily: "var(--font-mono)",
                    color: "var(--cc-muted)",
                    flexShrink: 0,
                    minWidth: 56,
                    textAlign: "right",
                  }}
                >
                  {ts}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Summary row */}
      {agents.length > 0 && (
        <div
          style={{
            display: "flex",
            gap: 16,
            borderTop: "1px solid rgba(255,255,255,0.05)",
            marginTop: 8,
            paddingTop: 8,
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 10, color: "var(--cc-muted)" }}>
            Total: {agents.length}
          </span>
          <span style={{ fontSize: 10, color: "#22c55e" }}>
            Executing: {executingCount}
          </span>
          <span
            style={{ fontSize: 10, color: "var(--color-text-secondary)" }}
          >
            Avg Success: {avgSuccess}%
          </span>
        </div>
      )}
    </div>
  );
}
