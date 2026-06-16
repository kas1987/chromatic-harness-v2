"use client";

import { AgentProfile } from "@/lib/api";
import { useTheme } from "@/lib/theme";

function levelBadge(level: number, accent: string, success: string): string {
  return level === 0 ? "#555" : level === 1 ? accent : level === 2 ? accent
    : level === 3 ? accent : level === 4 ? success : success;
}

function riskColor(score: number, danger: string, warning: string, success: string): string {
  return score > 0.7 ? danger : score > 0.4 ? warning : success;
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
  const { theme } = useTheme();
  const selected = selectedAgent ?? null;

  const PANEL: React.CSSProperties = {
    border: `1px solid ${theme.panelBorder}`,
    borderRadius: 4,
    padding: 12,
    marginBottom: 16,
    background: theme.panelBg,
  };

  const HEADING: React.CSSProperties = {
    fontSize: 12,
    fontWeight: "bold",
    color: theme.muted,
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

  return (
    <div style={PANEL}>
      <p style={HEADING}>Agent Trust Profiles</p>
      {agents.length === 0 && <p style={{ color: theme.muted, fontSize: 12 }}>No agents registered.</p>}

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
                background: selected?.agent_id === a.agent_id ? "#1a2a3a" : theme.panelBg,
                cursor: "pointer",
                fontSize: 12,
                border: "1px solid " + (selected?.agent_id === a.agent_id ? theme.accent : theme.panelBorder),
              }}
            >
              <div style={{ display: "flex", alignItems: "center", marginBottom: 4 }}>
                <span style={{ color: theme.accent }}>{a.agent_id}</span>
                <span style={BADGE(levelBadge(a.current_level, theme.accent, theme.success))}>L{a.current_level}</span>
              </div>
              <div style={{ color: theme.muted, fontSize: 10 }}>
                Success: {(a.success_rate * 100).toFixed(0)}% · Risk: {(a.risk_score * 100).toFixed(0)}%
              </div>
            </div>
          ))}
        </div>

        {/* Selected Agent Details */}
        {selected && (
          <div style={{ fontSize: 11 }}>
            <div style={{ marginBottom: 10 }}>
              <div style={{ color: theme.muted, marginBottom: 4 }}>Current Level</div>
              <div style={{ fontSize: 14, color: theme.text }}>L{selected.current_level}</div>
              <div style={{ color: theme.muted, marginTop: 2 }}>Executions: {selected.total_executions}</div>
            </div>

            <div style={{ marginBottom: 10 }}>
              <div style={{ color: theme.muted, marginBottom: 4 }}>Success Rate</div>
              <div style={{ height: 8, background: theme.panelBg, borderRadius: 4, overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${selected.success_rate * 100}%`,
                    background: selected.success_rate > 0.8 ? theme.success : theme.warning,
                  }}
                />
              </div>
              <div style={{ color: theme.text, marginTop: 2 }}>{(selected.success_rate * 100).toFixed(0)}%</div>
            </div>

            <div style={{ marginBottom: 10 }}>
              <div style={{ color: theme.muted, marginBottom: 4 }}>Risk Score</div>
              <div style={{ height: 8, background: theme.panelBg, borderRadius: 4, overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${selected.risk_score * 100}%`,
                    background: riskColor(selected.risk_score, theme.danger, theme.warning, theme.success),
                  }}
                />
              </div>
              <div style={{ color: riskColor(selected.risk_score, theme.danger, theme.warning, theme.success), marginTop: 2 }}>
                {(selected.risk_score * 100).toFixed(0)}%
              </div>
            </div>

            {selected.promotion_history.length > 0 && (
              <div>
                <div style={{ color: theme.muted, marginBottom: 4 }}>Promotion History</div>
                {selected.promotion_history.map((p, i) => (
                  <div key={i} style={{ color: theme.muted, fontSize: 10, marginBottom: 2 }}>
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
