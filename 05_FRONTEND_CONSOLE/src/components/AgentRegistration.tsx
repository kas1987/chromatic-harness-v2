"use client";

import { useState, useEffect } from "react";
import {
  registerAgent,
  promoteAgent,
  getLevelThresholds,
  type AgentProfile,
  type LevelThreshold,
} from "@/lib/api";
import { useTheme } from "@/lib/theme";

const LEVEL_LABELS: Record<number, string> = {
  0: "Observer",
  1: "Apprentice",
  2: "Practitioner",
  3: "Senior",
  4: "Lead",
  5: "Sovereign",
};

function PromotionTimeline({
  agent,
  thresholds,
  onPromote,
  theme,
}: {
  agent: AgentProfile;
  thresholds: Record<string, LevelThreshold>;
  onPromote: (level: number, reason: string) => void;
  theme: ReturnType<typeof useTheme>["theme"];
}) {
  const [promoting, setPromoting] = useState(false);
  const [promoteReason, setPromoteReason] = useState("");

  const INPUT: React.CSSProperties = {
    background: theme.panelBg,
    border: `1px solid ${theme.panelBorder}`,
    color: theme.text,
    padding: "4px 8px",
    borderRadius: 3,
    fontFamily: "monospace",
    fontSize: 12,
    width: "100%",
    boxSizing: "border-box" as const,
  };

  const BTN = (color = theme.accent): React.CSSProperties => ({
    background: color,
    border: "none",
    color: "#fff",
    padding: "4px 10px",
    borderRadius: 3,
    cursor: "pointer",
    fontFamily: "monospace",
    fontSize: 12,
  });

  // Level colors: L0 muted, L1-L3 accent (blues), L4-L5 success (greens)
  const LEVEL_COLOR: Record<number, string> = {
    0: theme.muted,
    1: theme.accent,
    2: theme.accent,
    3: theme.accent,
    4: theme.success,
    5: theme.success,
  };

  const nextLevel = Math.min(5, agent.current_level + 1);
  const nextThresh = thresholds[String(nextLevel)];

  const canPromote = nextThresh
    ? agent.total_executions >= nextThresh.min_executions &&
      agent.success_rate >= nextThresh.min_success_rate &&
      agent.risk_score <= nextThresh.max_risk
    : false;

  return (
    <div style={{ marginTop: 8 }}>
      {/* Level rail */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 0,
          marginBottom: 12,
          position: "relative",
        }}
      >
        {[0, 1, 2, 3, 4, 5].map((lvl) => (
          <div key={lvl} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: lvl <= agent.current_level ? LEVEL_COLOR[lvl] : theme.panelBg,
                border: `2px solid ${lvl === agent.current_level ? LEVEL_COLOR[lvl] : theme.panelBorder}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 11,
                fontWeight: "bold",
                color: lvl <= agent.current_level ? "#fff" : theme.muted,
                zIndex: 1,
                position: "relative",
              }}
            >
              {lvl}
            </div>
            <div style={{ fontSize: 9, color: lvl === agent.current_level ? LEVEL_COLOR[lvl] : theme.muted, marginTop: 3 }}>
              {LEVEL_LABELS[lvl]}
            </div>
            {/* connector */}
            {lvl < 5 && (
              <div
                style={{
                  position: "absolute",
                  height: 2,
                  background: lvl < agent.current_level ? LEVEL_COLOR[lvl] : theme.panelBorder,
                  width: "calc(100% - 28px)",
                  left: "calc(50% + 14px)",
                  top: 13,
                  zIndex: 0,
                }}
              />
            )}
          </div>
        ))}
      </div>

      {/* Next level requirements */}
      {agent.current_level < 5 && nextThresh && (
        <div
          style={{
            background: theme.panelBg,
            border: `1px solid ${theme.panelBorder}`,
            borderRadius: 3,
            padding: "8px 10px",
            fontSize: 11,
            marginBottom: 8,
          }}
        >
          <div style={{ color: theme.muted, marginBottom: 4 }}>
            Requirements for L{nextLevel} ({LEVEL_LABELS[nextLevel]}):
          </div>
          <div
            style={{
              color:
                agent.total_executions >= nextThresh.min_executions
                  ? theme.success
                  : theme.warning,
            }}
          >
            Executions: {agent.total_executions} / {nextThresh.min_executions}
          </div>
          <div
            style={{
              color:
                agent.success_rate >= nextThresh.min_success_rate
                  ? theme.success
                  : theme.warning,
            }}
          >
            Success rate: {(agent.success_rate * 100).toFixed(0)}% /{" "}
            {(nextThresh.min_success_rate * 100).toFixed(0)}%
          </div>
          <div
            style={{
              color:
                agent.risk_score <= nextThresh.max_risk ? theme.success : theme.danger,
            }}
          >
            Risk score: {(agent.risk_score * 100).toFixed(0)}% ≤{" "}
            {(nextThresh.max_risk * 100).toFixed(0)}%
          </div>
        </div>
      )}

      {/* Promote action */}
      {agent.current_level < 5 && (
        <div>
          {!promoting ? (
            <button
              onClick={() => setPromoting(true)}
              disabled={!canPromote}
              style={{
                ...BTN(canPromote ? theme.success : theme.panelBorder),
                opacity: canPromote ? 1 : 0.5,
                cursor: canPromote ? "pointer" : "not-allowed",
              }}
            >
              {canPromote ? `Promote → L${nextLevel}` : `L${nextLevel} locked`}
            </button>
          ) : (
            <div style={{ display: "flex", gap: 6 }}>
              <input
                value={promoteReason}
                onChange={(e) => setPromoteReason(e.target.value)}
                placeholder="Reason for promotion…"
                style={{ ...INPUT, flex: 1 }}
                autoFocus
              />
              <button
                onClick={() => {
                  if (promoteReason.trim()) {
                    onPromote(nextLevel, promoteReason.trim());
                    setPromoting(false);
                    setPromoteReason("");
                  }
                }}
                style={BTN(theme.success)}
              >
                Confirm
              </button>
              <button
                onClick={() => setPromoting(false)}
                style={BTN(theme.danger)}
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      )}

      {/* Promotion history */}
      {agent.promotion_history && agent.promotion_history.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ color: theme.muted, fontSize: 10, marginBottom: 4 }}>
            HISTORY
          </div>
          {[...agent.promotion_history].reverse().map((p, i) => (
            <div key={i} style={{ fontSize: 10, color: theme.muted, marginBottom: 2 }}>
              → L{p.level} ·{" "}
              {new Date(p.date).toLocaleDateString()} · {p.reason}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AgentRegistration({
  onAgentRegistered,
  selectedAgent,
}: {
  onAgentRegistered?: (agent: AgentProfile) => void;
  selectedAgent?: AgentProfile | null;
}) {
  const { theme } = useTheme();
  const [agentId, setAgentId] = useState("");
  const [description, setDescription] = useState("");
  const [initialLevel, setInitialLevel] = useState(0);
  const [error, setError] = useState("");
  const [thresholds, setThresholds] = useState<Record<string, LevelThreshold>>(
    {}
  );

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

  const INPUT: React.CSSProperties = {
    background: theme.panelBg,
    border: `1px solid ${theme.panelBorder}`,
    color: theme.text,
    padding: "4px 8px",
    borderRadius: 3,
    fontFamily: "monospace",
    fontSize: 12,
    width: "100%",
    boxSizing: "border-box" as const,
  };

  const BTN = (color = theme.accent): React.CSSProperties => ({
    background: color,
    border: "none",
    color: "#fff",
    padding: "4px 10px",
    borderRadius: 3,
    cursor: "pointer",
    fontFamily: "monospace",
    fontSize: 12,
  });

  useEffect(() => {
    getLevelThresholds()
      .then(setThresholds)
      .catch(() => {});
  }, []);

  async function handleRegister() {
    setError("");
    if (!agentId.trim()) {
      setError("Agent ID is required");
      return;
    }
    try {
      const agent = await registerAgent({
        agent_id: agentId.trim(),
        description: description.trim(),
        initial_level: initialLevel,
      });
      setAgentId("");
      setDescription("");
      setInitialLevel(0);
      onAgentRegistered?.(agent);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Registration failed");
    }
  }

  async function handlePromote(newLevel: number, reason: string) {
    if (!selectedAgent) return;
    try {
      const updated = await promoteAgent(selectedAgent.agent_id, newLevel, reason);
      onAgentRegistered?.(updated);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Promotion failed");
    }
  }

  return (
    <div style={PANEL}>
      <p style={HEADING}>Agent Registration</p>

      {/* Registration form */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 6, marginBottom: 6 }}>
          <input
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleRegister()}
            placeholder="agent-id (e.g. kimi-builder)"
            style={INPUT}
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)"
            style={INPUT}
          />
          <select
            value={initialLevel}
            onChange={(e) => setInitialLevel(Number(e.target.value))}
            style={{ ...INPUT, width: "auto" }}
          >
            {[0, 1, 2, 3, 4, 5].map((l) => (
              <option key={l} value={l}>
                L{l} — {LEVEL_LABELS[l]}
              </option>
            ))}
          </select>
        </div>
        <button onClick={handleRegister} style={BTN()}>
          Register Agent
        </button>
        {error && (
          <span style={{ color: theme.danger, fontSize: 11, marginLeft: 8 }}>
            {error}
          </span>
        )}
      </div>

      {/* Promotion timeline for selected agent */}
      {selectedAgent && (
        <div>
          <div
            style={{
              borderTop: `1px solid ${theme.panelBorder}`,
              paddingTop: 10,
              marginTop: 4,
            }}
          >
            <div style={{ color: theme.muted, fontSize: 11, marginBottom: 6 }}>
              Promotion timeline —{" "}
              <span style={{ color: theme.accent }}>{selectedAgent.agent_id}</span>
            </div>
            <PromotionTimeline
              agent={selectedAgent}
              thresholds={thresholds}
              onPromote={handlePromote}
              theme={theme}
            />
          </div>
        </div>
      )}
    </div>
  );
}
