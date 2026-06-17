"use client";

import type { Mission, MagnetEvent } from "@/lib/api";
import type { HarnessGoMode } from "@/hooks/useHarnessData";

interface ConfidenceGateProps {
  mission: Mission | null;
  events: MagnetEvent[];
  goMode?: HarnessGoMode | null;
}

export default function ConfidenceGate({ mission, events, goMode }: ConfidenceGateProps) {
  const pct = goMode?.confidence?.score ?? mission?.confidence_score ?? 0;
  const riskEvents = events.filter((e) => e.risk_delta > 0.1).length;

  const gateDecision =
    pct >= 90
      ? "AUTO-PROCEED"
      : pct >= 70
      ? "PROCEED"
      : pct >= 50
      ? "CAUTION"
      : "STOP / REPLAN";

  const gateColor =
    pct >= 90
      ? "#22c55e"
      : pct >= 70
      ? "#8b5cf6"
      : pct >= 50
      ? "#f59e0b"
      : "#ef4444";

  const humanGate = pct < 70 ? "Required" : "Not Required";
  const allowedAction =
    pct >= 70 ? "Scoped Execution" : pct >= 50 ? "Read Only" : "Halt";

  const liveFactors = goMode?.confidence?.factors;
  const FACTORS = [
    { label: "Objective Clarity", value: liveFactors?.objective_clarity ?? Math.min(100, Math.max(0, pct + 14)) },
    { label: "Scope Clarity", value: liveFactors?.scope_clarity ?? Math.min(100, Math.max(0, pct + 7)) },
    { label: "Evidence Quality", value: liveFactors?.evidence_quality ?? Math.min(100, Math.max(0, pct - 5 + events.length * 2)) },
    { label: "Reversibility", value: liveFactors?.reversibility ?? Math.min(100, Math.max(0, pct + 12)) },
    { label: "Risk Awareness", value: liveFactors?.risk_awareness ?? Math.min(100, Math.max(0, pct - 8 + riskEvents * -3)) },
    { label: "Tool Fit", value: liveFactors?.tool_fit ?? Math.min(100, Math.max(0, pct + 16)) },
    { label: "Testability", value: liveFactors?.testability ?? Math.min(100, Math.max(0, pct + 4)) },
  ];

  const factorColor = (value: number) =>
    value >= 80
      ? "#22c55e"
      : value >= 60
      ? "#8b5cf6"
      : value >= 40
      ? "#f59e0b"
      : "#ef4444";

  const circumference = 389.56;
  const strokeDasharray = `${(pct / 100) * circumference} ${circumference}`;

  return (
    <div className="cc-panel">
      <div className="cc-panel-title">CONFIDENCE &amp; GATE</div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "160px 1fr",
          gap: "16px",
          alignItems: "start",
        }}
      >
        {/* Left: SVG Donut Gauge */}
        <div style={{ display: "flex", justifyContent: "center" }}>
          <svg
            viewBox="0 0 160 160"
            width={160}
            height={160}
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Background circle */}
            <circle
              cx={80}
              cy={80}
              r={62}
              fill="none"
              stroke="#1e293b"
              strokeWidth={14}
            />
            {/* Progress arc */}
            <circle
              cx={80}
              cy={80}
              r={62}
              fill="none"
              stroke={gateColor}
              strokeWidth={14}
              strokeDasharray={strokeDasharray}
              strokeLinecap="round"
              transform="rotate(-90 80 80)"
              style={{ transition: "stroke-dasharray 0.6s ease" }}
            />
            {/* Center percentage */}
            <text
              x={80}
              y={76}
              textAnchor="middle"
              fontSize={28}
              fontWeight={700}
              fill={gateColor}
              fontFamily="var(--font-mono, monospace)"
            >
              {pct}%
            </text>
            {/* Center subtext */}
            <text
              x={80}
              y={94}
              textAnchor="middle"
              fontSize={10}
              fill="#475569"
              fontFamily="var(--font-body, sans-serif)"
            >
              Confidence Score
            </text>
          </svg>
        </div>

        {/* Right: Factor bars */}
        <div>
          {FACTORS.map((factor) => {
            const color = factorColor(factor.value);
            return (
              <div key={factor.label} style={{ marginBottom: "8px" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "4px",
                  }}
                >
                  <span
                    style={{
                      fontSize: "10px",
                      color: "var(--cc-muted, #475569)",
                    }}
                  >
                    {factor.label}
                  </span>
                  <span
                    style={{
                      fontSize: "10px",
                      fontWeight: 700,
                      color,
                    }}
                  >
                    {factor.value}
                  </span>
                </div>
                <div className="cc-progress-bar cc-progress-bar-lg">
                  <div
                    className="cc-progress-fill"
                    style={{
                      background: color,
                      width: `${factor.value}%`,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Gate decision section */}
      <div
        style={{
          borderTop: "1px solid var(--color-border, #1e293b)",
          paddingTop: "12px",
          marginTop: "12px",
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
        }}
      >
        {/* Box 1: Gate Decision */}
        <div>
          <div
            style={{
              fontSize: "9px",
              color: "var(--cc-muted, #475569)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              marginBottom: "4px",
            }}
          >
            GATE DECISION
          </div>
          <div
            style={{
              fontSize: "18px",
              fontWeight: 700,
              color: gateColor,
              letterSpacing: "-0.02em",
            }}
          >
            {gateDecision}
          </div>
        </div>

        {/* Box 2: Allowed Action */}
        <div>
          <div
            style={{
              fontSize: "9px",
              color: "var(--cc-muted, #475569)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              marginBottom: "4px",
            }}
          >
            Allowed Action
          </div>
          <div
            style={{
              fontSize: "12px",
              color: "var(--color-text-primary, #f8fafc)",
            }}
          >
            {allowedAction}
          </div>
        </div>

        {/* Box 3: Human Gate */}
        <div>
          <div
            style={{
              fontSize: "9px",
              color: "var(--cc-muted, #475569)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              marginBottom: "4px",
            }}
          >
            Human Gate
          </div>
          <div
            style={{
              fontSize: "12px",
              color: humanGate === "Required" ? "#f59e0b" : "#22c55e",
            }}
          >
            {humanGate}
          </div>
        </div>
      </div>
      {goMode && (
        <div style={{ marginTop: 8, fontSize: 11, color: goMode.dispatch_allowed ? '#22c55e' : '#f59e0b', display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontFamily: 'monospace' }}>DISPATCH:</span>
          <span style={{ fontWeight: 600 }}>{goMode.dispatch_allowed ? 'ALLOWED' : 'BLOCKED'}</span>
          {goMode.selected && <span style={{ color: '#94a3b8', fontSize: 10 }}>{goMode.selected.id}</span>}
        </div>
      )}
    </div>
  );
}
