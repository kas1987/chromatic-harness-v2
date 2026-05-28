"use client";

import { AgentProfile } from "@/lib/api";

const PANEL: React.CSSProperties = {
  border: "1px solid #333",
  borderRadius: 4,
  padding: 12,
  marginBottom: 16,
  background: "#111",
};

const HEADING: React.CSSProperties = {
  fontSize: 12,
  fontWeight: "bold",
  color: "#888",
  textTransform: "uppercase",
  letterSpacing: 1,
  marginBottom: 8,
  marginTop: 0,
};

const BADGE = (color: string): React.CSSProperties => ({
  display: "inline-block",
  padding: "1px 6px",
  borderRadius: 3,
  background: color,
  color: "#fff",
  fontSize: 11,
  marginLeft: 6,
});

function levelBadge(level: number): string {
  return level === 0 ? "#555" : level === 1 ? "#39e" : level === 2 ? "#3ce" 
    : level === 3 ? "#3ae" : level === 4 ? "#2a8" : "#1a7";
}

function riskColor(score: number): string {
  return score > 0.7 ? "#e53" : score > 0.4 ? "#e93" : "#1a7";
}

export default function AgentProfiles({
  agents,
  selectedAgent,
  onSelect,
}: {
  agents: AgentProfile[];
  selectedAgent?: AgentProfile | null;
  onSelect?: (agent: AgentProfile) => void;
}) {
  const selected = selectedAgent ?? null;

  return (
    <div style={PANEL}>
      <p style={HEADING}>Agent Trust Profiles</p>
      {agents.length === 0 && <p style={{ color: "#555", fontSize: 12 }}>No agents registered.</p>}
      
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {/* Agent List */}
        <div>
          {agents.map(a => (
            <div
              key={a.agent_id}
              onClick={() => onSelect?.(a)}
              style={{
                padding: "8px",
                marginBottom: 6,
                borderRadius: 3,
                background: selected?.agent_id === a.agent_id ? "#1a2a3a" : "#1a1a1a",
                cursor: "pointer",
                fontSize: 12,
                border: "1px solid " + (selected?.agent_id === a.agent_id ? "#39e" : "#222"),
              }}
            >
              <div style={{ display: "flex", alignItems: "center", marginBottom: 4 }}>
                <span style={{ color: "#39e" }}>{a.agent_id}</span>
                <span style={BADGE(levelBadge(a.current_level))}>L{a.current_level}</span>
              </div>
              <div style={{ color: "#555", fontSize: 10 }}>
                Success: {(a.success_rate * 100).toFixed(0)}% · Risk: {(a.risk_score * 100).toFixed(0)}%
              </div>
            </div>
          ))}
        </div>

        {/* Selected Agent Details */}
        {selected && (
          <div style={{ fontSize: 11 }}>
            <div style={{ marginBottom: 10 }}>
              <div style={{ color: "#888", marginBottom: 4 }}>Current Level</div>
              <div style={{ fontSize: 14, color: "#e0e0e0" }}>L{selected.current_level}</div>
              <div style={{ color: "#555", marginTop: 2 }}>Executions: {selected.total_executions}</div>
            </div>

            <div style={{ marginBottom: 10 }}>
              <div style={{ color: "#888", marginBottom: 4 }}>Success Rate</div>
              <div style={{ height: 8, background: "#1a1a1a", borderRadius: 4, overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${selected.success_rate * 100}%`,
                    background: selected.success_rate > 0.8 ? "#1a7" : "#8a4a1a",
                  }}
                />
              </div>
              <div style={{ color: "#aaa", marginTop: 2 }}>{(selected.success_rate * 100).toFixed(0)}%</div>
            </div>

            <div style={{ marginBottom: 10 }}>
              <div style={{ color: "#888", marginBottom: 4 }}>Risk Score</div>
              <div style={{ height: 8, background: "#1a1a1a", borderRadius: 4, overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${selected.risk_score * 100}%`,
                    background: riskColor(selected.risk_score),
                  }}
                />
              </div>
              <div style={{ color: riskColor(selected.risk_score), marginTop: 2 }}>
                {(selected.risk_score * 100).toFixed(0)}%
              </div>
            </div>

            {selected.promotion_history.length > 0 && (
              <div>
                <div style={{ color: "#888", marginBottom: 4 }}>Promotion History</div>
                {selected.promotion_history.map((p, i) => (
                  <div key={i} style={{ color: "#555", fontSize: 10, marginBottom: 2 }}>
                    → L{p.level} · {new Date(p.date).toLocaleDateString()} · {p.reason}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
