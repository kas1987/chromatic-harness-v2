"use client";

import React, { useState } from "react";

interface Mission {
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

interface MagnetEvent {
  event_id: string;
  mission_id: string;
  magnet_name: string;
  inflection_point: string;
  risk_delta: number;
  recommended_action: string;
  timestamp: string;
}

interface Bead {
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

interface SynthesisResult {
  mission_id: string;
  recommendation: string;
  confidence_score: number;
  risk_level: string;
  summary: string;
  bead_created?: boolean;
}

interface MagnetsConsoleProps {
  mission: Mission | null;
  events: MagnetEvent[];
}

const MAGNETS = [
  { id: "intake",     label: "INTAKE MAGNET",     color: "#14b8a6", icon: "⊍" },
  { id: "scope",      label: "SCOPE MAGNET",       color: "#facc15", icon: "⊍" },
  { id: "execution",  label: "EXECUTION MAGNET",   color: "#22c55e", icon: "⊍" },
  { id: "cost",       label: "COST MAGNET",        color: "#f59e0b", icon: "⊍" },
  { id: "security",   label: "SECURITY MAGNET",    color: "#ef4444", icon: "⊍" },
  { id: "validation", label: "VALIDATION MAGNET",  color: "#3b82f6", icon: "⊍" },
  { id: "decision",   label: "DECISION MAGNET",    color: "#8b5cf6", icon: "⊍" },
  { id: "closure",    label: "CLOSURE MAGNET",     color: "#a855f7", icon: "⊍" },
];

function getSecondsAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function getMagnetColor(magnetName: string): string {
  const lower = magnetName.toLowerCase();
  const match = MAGNETS.find((m) => lower.includes(m.id));
  return match ? match.color : "#94a3b8";
}

function getMagnetHealth(mag: { id: string }, events: MagnetEvent[]) {
  const magnetEvents = events.filter((e) =>
    e.magnet_name.toLowerCase().includes(mag.id)
  );
  const highRisk = magnetEvents.filter((e) => e.risk_delta > 0.1);
  const status =
    highRisk.length >= 2
      ? "Critical"
      : highRisk.length === 1
      ? "Warning"
      : "Healthy";
  const confidenceDelta =
    status === "Healthy" ? "+2%" : status === "Warning" ? "-3%" : "-8%";
  const lastEvent =
    magnetEvents[magnetEvents.length - 1]?.inflection_point || "Full Visibility";
  const eventCount = magnetEvents.length;
  const lastTimestamp = magnetEvents[magnetEvents.length - 1]?.timestamp;
  return { status, confidenceDelta, lastEvent, eventCount, lastTimestamp };
}

function StatusDot({ status }: { status: string }) {
  if (status === "Healthy") return <span className="cc-dot-live" />;
  if (status === "Warning") return <span className="cc-dot-warn" />;
  return <span className="cc-dot-err" />;
}

function HealthFill({ status }: { status: string }) {
  const pct = status === "Healthy" ? 80 : status === "Warning" ? 40 : 15;
  const color =
    status === "Healthy"
      ? "var(--color-success)"
      : status === "Warning"
      ? "var(--color-warning)"
      : "var(--color-error)";
  return (
    <div className="cc-progress-bar" style={{ marginTop: 6 }}>
      <div
        className="cc-progress-fill"
        style={{ width: `${pct}%`, background: color }}
      />
    </div>
  );
}

function ConfidenceBadge({ delta }: { delta: string }) {
  const isPos = delta.startsWith("+");
  const color = isPos
    ? "var(--color-success)"
    : delta === "-3%"
    ? "var(--color-warning)"
    : "var(--color-error)";
  return (
    <span
      style={{
        fontSize: 8,
        fontFamily: "var(--font-mono)",
        color,
        border: `1px solid ${color}`,
        borderRadius: 3,
        padding: "1px 4px",
        fontWeight: 700,
      }}
    >
      {delta}
    </span>
  );
}

export default function MagnetsConsole({ mission, events }: MagnetsConsoleProps) {
  const [filter, setFilter] = useState("all");

  const recentStream = [...events]
    .sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    )
    .slice(0, 4);

  const filteredMagnets =
    filter === "all"
      ? MAGNETS
      : MAGNETS.filter((m) => m.id === filter);

  const lastFiveEvents = [...events]
    .sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    )
    .slice(0, 5);

  return (
    <div className="cc-panel" style={{ padding: "12px 14px" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 6,
        }}
      >
        <span
          className="cc-panel-title"
          style={{ color: "#facc15", letterSpacing: "0.08em" }}
        >
          MAGNETS CONSOLE
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            style={{
              fontSize: 9,
              fontFamily: "var(--font-mono)",
              background: "rgba(0,0,0,0.4)",
              color: "var(--cc-muted)",
              border: "1px solid var(--cc-panel-border)",
              borderRadius: 4,
              padding: "2px 6px",
              cursor: "pointer",
            }}
          >
            <option value="all">All Magnets</option>
            {MAGNETS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
          <span
            className="chromatic-badge chromatic-badge-success"
            style={{ fontSize: 8, padding: "2px 6px", letterSpacing: "0.1em" }}
          >
            LIVE
          </span>
        </div>
      </div>

      {/* Event Stream Mini Header */}
      {recentStream.length > 0 && (
        <div
          style={{
            background: "rgba(0,0,0,0.2)",
            borderRadius: 4,
            padding: "5px 8px",
            marginBottom: 8,
            display: "flex",
            flexDirection: "column",
            gap: 2,
          }}
        >
          {recentStream.map((ev) => {
            const col = getMagnetColor(ev.magnet_name);
            return (
              <div
                key={ev.event_id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 9,
                  fontFamily: "var(--font-mono)",
                  color: "var(--cc-muted)",
                  lineHeight: 1.4,
                }}
              >
                <span style={{ color: col, flexShrink: 0 }}>▸</span>
                <span
                  style={{
                    color: col,
                    fontWeight: 700,
                    flexShrink: 0,
                    textTransform: "uppercase",
                  }}
                >
                  {ev.magnet_name}
                </span>
                <span
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    flex: 1,
                  }}
                >
                  {ev.inflection_point}
                </span>
                <span style={{ flexShrink: 0, color: "var(--cc-muted)" }}>
                  {getSecondsAgo(ev.timestamp)}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Magnet Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 8,
          marginTop: 4,
        }}
      >
        {filteredMagnets.map((mag) => {
          const { status, confidenceDelta, lastEvent, eventCount, lastTimestamp } =
            getMagnetHealth(mag, events);

          return (
            <div
              key={mag.id}
              style={{
                padding: 10,
                borderRadius: 6,
                borderLeft: `3px solid ${mag.color}`,
                background: "rgba(0,0,0,0.25)",
                position: "relative",
                minWidth: 0,
              }}
            >
              {/* Row 1: icon + label / status */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 4,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    minWidth: 0,
                  }}
                >
                  <span style={{ color: mag.color, fontSize: 12, flexShrink: 0 }}>
                    {mag.icon}
                  </span>
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      color: mag.color,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                      fontFamily: "var(--font-mono)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {mag.label}
                  </span>
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 3,
                    flexShrink: 0,
                  }}
                >
                  <StatusDot status={status} />
                  <span
                    style={{
                      fontSize: 9,
                      fontFamily: "var(--font-mono)",
                      color:
                        status === "Healthy"
                          ? "var(--color-success)"
                          : status === "Warning"
                          ? "var(--color-warning)"
                          : "var(--color-error)",
                    }}
                  >
                    {status}
                  </span>
                </div>
              </div>

              {/* Row 2: lastEvent */}
              <div
                style={{
                  fontSize: 9,
                  color: "var(--cc-muted)",
                  marginTop: 3,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  fontFamily: "var(--font-mono)",
                }}
                title={lastEvent}
              >
                {lastEvent}
              </div>

              {/* Row 3: time ago + confidence delta */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginTop: 4,
                  gap: 4,
                }}
              >
                <span
                  style={{
                    fontSize: 9,
                    color: "var(--cc-muted)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {lastTimestamp
                    ? `Last Event: ${getSecondsAgo(lastTimestamp)}`
                    : `${eventCount} event${eventCount !== 1 ? "s" : ""}`}
                </span>
                <ConfidenceBadge delta={confidenceDelta} />
              </div>

              {/* Row 4: progress bar */}
              <HealthFill status={status} />
            </div>
          );
        })}
      </div>

      {/* Magnet Event Stream Section */}
      {lastFiveEvents.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div
            style={{
              fontSize: 9,
              color: "var(--cc-muted)",
              fontFamily: "var(--font-mono)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              marginBottom: 6,
            }}
          >
            MAGNET EVENT STREAM
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {lastFiveEvents.map((ev) => {
              const col = getMagnetColor(ev.magnet_name);
              const riskColor =
                ev.risk_delta > 0.1
                  ? "var(--color-error)"
                  : ev.risk_delta > 0
                  ? "var(--color-warning)"
                  : "var(--color-success)";
              const riskLabel =
                ev.risk_delta > 0
                  ? `+${(ev.risk_delta * 100).toFixed(0)}%`
                  : `${(ev.risk_delta * 100).toFixed(0)}%`;

              return (
                <div
                  key={ev.event_id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "4px 6px",
                    borderRadius: 4,
                    background: "rgba(0,0,0,0.15)",
                    fontSize: 9,
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  <span style={{ color: col, fontSize: 10, flexShrink: 0 }}>●</span>
                  <span
                    style={{
                      color: col,
                      fontWeight: 700,
                      flexShrink: 0,
                      textTransform: "uppercase",
                      minWidth: 70,
                    }}
                  >
                    {ev.magnet_name}
                  </span>
                  <span
                    style={{
                      color: "var(--cc-text)",
                      flex: 1,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={ev.inflection_point}
                  >
                    {ev.inflection_point}
                  </span>
                  <span
                    style={{
                      color: riskColor,
                      fontWeight: 700,
                      flexShrink: 0,
                      minWidth: 36,
                      textAlign: "right",
                    }}
                  >
                    {riskLabel}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty state */}
      {events.length === 0 && (
        <div
          style={{
            textAlign: "center",
            color: "var(--cc-muted)",
            fontSize: 10,
            fontFamily: "var(--font-mono)",
            padding: "16px 0 4px",
          }}
        >
          No magnet events — awaiting mission activation
        </div>
      )}
    </div>
  );
}
