"use client";

import React, { useState } from "react";

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

// Layer palette
const COLORS = {
  cmp: "#8b5cf6",
  runtime: "#3b82f6",
  mcp: "#22c55e",
  magnets: "#facc15",
  beads: "#14b8a6",
  risk: "#ef4444",
};

interface PipelineStep {
  number: number;
  layer: keyof typeof COLORS;
  title: string;
  subtitle: string;
}

const STEPS: PipelineStep[] = [
  { number: 1, layer: "cmp", title: "INTENT", subtitle: "GO Command Received" },
  { number: 2, layer: "cmp", title: "MISSION PACKET", subtitle: "Packet Built (CMP)" },
  { number: 3, layer: "cmp", title: "CMP GATE", subtitle: "Policy & Confidence" },
  { number: 4, layer: "runtime", title: "ROUTER", subtitle: "Agent Selection" },
  { number: 5, layer: "runtime", title: "AGENT RUNTIME", subtitle: "Execution" },
  { number: 6, layer: "mcp", title: "MCP TOOLS", subtitle: "Tool Calls" },
  { number: 7, layer: "magnets", title: "MAGNETS", subtitle: "Observability" },
  { number: 8, layer: "runtime", title: "VALIDATION", subtitle: "Verify & Test" },
  { number: 9, layer: "beads", title: "BEADS INTAKE", subtitle: "Findings to Work" },
  { number: 10, layer: "cmp", title: "REPORT", subtitle: "Synthesis" },
  { number: 11, layer: "runtime", title: "CONTINUE", subtitle: "Next Step" },
];

type StepStatus = "complete" | "active" | "failed" | "pending";

function deriveStepStatuses(
  mission: Mission | null,
  events: MagnetEvent[]
): StepStatus[] {
  if (!mission) {
    return STEPS.map(() => "pending");
  }

  const statuses: StepStatus[] = STEPS.map(() => "pending");

  if (mission.status === "pending") {
    statuses[0] = "complete";
  } else if (mission.status === "running") {
    const completeCount = Math.floor(events.length / 1.5 + 1);
    for (let i = 0; i < STEPS.length; i++) {
      if (i < completeCount) {
        statuses[i] = "complete";
      } else if (i === completeCount) {
        statuses[i] = "active";
        break;
      }
    }
  } else if (mission.status === "completed") {
    return STEPS.map(() => "complete");
  } else if (mission.status === "failed") {
    const completeCount = events.length;
    for (let i = 0; i < STEPS.length; i++) {
      if (i < completeCount) {
        statuses[i] = "complete";
      } else if (i === completeCount) {
        statuses[i] = "failed";
        break;
      }
    }
  }

  return statuses;
}

function formatTimestamp(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");
    return `${hh}:${mm}:${ss}`;
  } catch {
    return "";
  }
}

function getStepTimestamp(
  stepIndex: number,
  mission: Mission | null,
  events: MagnetEvent[],
  status: StepStatus
): string {
  if (status !== "complete" && status !== "active") return "";
  if (!mission) return "";

  if (stepIndex === 0 && mission.created_at) {
    return formatTimestamp(mission.created_at);
  }
  if (stepIndex === STEPS.length - 1 && mission.completed_at) {
    return formatTimestamp(mission.completed_at);
  }
  if (events.length > 0) {
    const eventIndex = Math.min(stepIndex, events.length - 1);
    if (events[eventIndex]?.timestamp) {
      return formatTimestamp(events[eventIndex].timestamp);
    }
  }
  if (mission.started_at) {
    return formatTimestamp(mission.started_at);
  }
  return formatTimestamp(mission.created_at);
}

interface StepCircleProps {
  stepNumber: number;
  status: StepStatus;
}

function StepCircle({ stepNumber, status }: StepCircleProps) {
  const baseStyle: React.CSSProperties = {
    width: 28,
    height: 28,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 11,
    fontWeight: "bold",
    fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
    borderWidth: 2,
    borderStyle: "solid",
    flexShrink: 0,
  };

  if (status === "complete") {
    return (
      <div
        style={{
          ...baseStyle,
          borderColor: "#22c55e",
          backgroundColor: "rgba(34,197,94,0.1)",
          color: "#22c55e",
        }}
      >
        ✓
      </div>
    );
  }
  if (status === "active") {
    return (
      <div
        style={{
          ...baseStyle,
          borderColor: "#8b5cf6",
          backgroundColor: "rgba(124,58,237,0.15)",
          color: "#a78bfa",
          boxShadow: "0 0 14px rgba(124,58,237,0.5)",
        }}
      >
        {stepNumber}
      </div>
    );
  }
  if (status === "failed") {
    return (
      <div
        style={{
          ...baseStyle,
          borderColor: "#ef4444",
          backgroundColor: "rgba(239,68,68,0.1)",
          color: "#ef4444",
        }}
      >
        ✕
      </div>
    );
  }
  // pending
  return (
    <div
      style={{
        ...baseStyle,
        borderColor: "#334155",
        backgroundColor: "rgba(51,65,85,0.2)",
        color: "#475569",
      }}
    >
      {stepNumber}
    </div>
  );
}

interface StepBoxProps {
  step: PipelineStep;
  status: StepStatus;
  timestamp: string;
}

function StepBox({ step, status, timestamp }: StepBoxProps) {
  const titleColor =
    status === "complete"
      ? "#22c55e"
      : status === "active"
      ? "#a78bfa"
      : status === "failed"
      ? "#ef4444"
      : "#475569";

  const opacity = status === "pending" && !timestamp ? 0.35 : 1;

  return (
    <div
      style={{
        minWidth: 108,
        maxWidth: 108,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        position: "relative",
        opacity,
      }}
    >
      <StepCircle stepNumber={step.number} status={status} />

      <div
        style={{
          fontSize: 9,
          color: "var(--cc-muted, #475569)",
          marginTop: 2,
          fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
        }}
      >
        {String(step.number).padStart(2, "0")}
      </div>

      <div
        style={{
          fontSize: 10,
          fontWeight: "bold",
          textTransform: "uppercase",
          textAlign: "center",
          marginTop: 4,
          color: titleColor,
          lineHeight: 1.2,
          display: "flex",
          alignItems: "center",
          gap: 3,
        }}
      >
        {status === "active" && <span className="cc-dot-live" style={{ flexShrink: 0 }} />}
        {step.title}
      </div>

      <div
        style={{
          fontSize: 9,
          color: "var(--cc-muted, #475569)",
          textAlign: "center",
          marginTop: 2,
          lineHeight: 1.3,
          padding: "0 2px",
        }}
      >
        {step.subtitle}
      </div>

      {(status === "complete" || status === "active") && timestamp && (
        <div
          style={{
            fontSize: 9,
            color: "var(--cc-muted, #475569)",
            fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
            marginTop: 3,
          }}
        >
          {timestamp}
        </div>
      )}
    </div>
  );
}

function ArrowConnector() {
  return (
    <div
      style={{
        width: 20,
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "#334155",
        fontSize: 12,
        alignSelf: "center",
        paddingTop: 8,
        userSelect: "none",
      }}
    >
      →
    </div>
  );
}

interface PipelineFlowProps {
  mission: Mission | null;
  events: MagnetEvent[];
}

export default function PipelineFlow({ mission, events }: PipelineFlowProps) {
  const [autoScroll, setAutoScroll] = useState(true);
  const [expanded, setExpanded] = useState(false);

  const statuses = deriveStepStatuses(mission, events);

  const noMission = !mission;

  return (
    <div
      className="cc-panel"
      style={{
        paddingBottom: 0,
        display: "flex",
        flexDirection: "column",
        gap: 0,
      }}
    >
      {/* Header row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 12,
        }}
      >
        <span
          className="cc-panel-title"
          style={{ fontSize: 11, letterSpacing: "0.1em", textTransform: "uppercase" }}
        >
          LIVE HARNESS PIPELINE
        </span>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              cursor: "pointer",
              fontSize: 9,
              color: "var(--cc-muted, #475569)",
              userSelect: "none",
            }}
          >
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              style={{ width: 10, height: 10, accentColor: "var(--cc-accent, #06b6d4)" }}
            />
            Auto-Scroll
          </label>

          <button
            onClick={() => setExpanded((v) => !v)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--cc-muted, #475569)",
              fontSize: 14,
              lineHeight: 1,
              padding: "0 2px",
            }}
            aria-label={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? "⊟" : "⊞"}
          </button>
        </div>
      </div>

      {/* Steps row */}
      <div
        className="cc-scrollable"
        style={{
          display: "flex",
          gap: 0,
          alignItems: "flex-start",
          paddingBottom: 8,
          overflowX: "auto",
          opacity: noMission ? 0.35 : 1,
          transition: "opacity 0.2s",
        }}
      >
        {STEPS.map((step, index) => {
          const status = noMission ? "pending" : statuses[index];
          const timestamp = getStepTimestamp(index, mission, events, status);

          return (
            <React.Fragment key={step.number}>
              <StepBox step={step} status={status} timestamp={timestamp} />
              {index < STEPS.length - 1 && <ArrowConnector />}
            </React.Fragment>
          );
        })}
      </div>

      {/* Feedback loop row */}
      <div
        style={{
          borderTop: "1px dashed #334155",
          paddingTop: 6,
          paddingBottom: 6,
          textAlign: "center",
          fontSize: 9,
          color: "var(--cc-muted, #475569)",
          fontStyle: "italic",
          letterSpacing: "0.05em",
        }}
      >
        ← FEEDBACK LOOP — CONTINUOUS IMPROVEMENT →
      </div>
    </div>
  );
}
