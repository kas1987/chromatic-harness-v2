"use client";

interface GovernancePanelProps {
  drift: unknown;
  security: unknown;
  unified_guard: unknown;
  tokens: unknown;
  loading: boolean;
}

function getDriftColor(score: number): string {
  if (score >= 90) return "#22c55e";
  if (score >= 70) return "#f59e0b";
  return "#ef4444";
}

function getStatusBadgeColor(status: string): string {
  if (status === "ok" || status === "healthy" || status === "green") return "#22c55e";
  if (status === "warning" || status === "degraded" || status === "yellow") return "#f59e0b";
  return "#ef4444";
}

function getQueueActionBadge(status: string): { label: string; color: string } {
  if (status === "skipped_existing") return { label: "EXISTS", color: "#64748b" };
  if (status === "created") return { label: "CREATED", color: "#22c55e" };
  if (status === "failed") return { label: "FAILED", color: "#ef4444" };
  return { label: status, color: "#64748b" };
}

export default function GovernancePanel({
  drift,
  security,
  unified_guard,
  tokens,
  loading,
}: GovernancePanelProps) {
  const panelStyle: React.CSSProperties = {
    background: "rgba(0,0,0,0.3)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 8,
    padding: 12,
    fontFamily: "monospace",
  };

  const separatorStyle: React.CSSProperties = {
    borderTop: "1px solid rgba(255,255,255,0.06)",
    margin: "8px 0",
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 11,
    color: "#64748b",
    letterSpacing: "1.5px",
    textTransform: "uppercase" as const,
  };

  const sectionLabelStyle: React.CSSProperties = {
    fontSize: 11,
    color: "#64748b",
    letterSpacing: "1px",
    textTransform: "uppercase" as const,
    minWidth: 70,
  };

  const valueStyle: React.CSSProperties = {
    fontSize: 12,
  };

  if (loading) {
    return (
      <div style={panelStyle}>
        <div style={{ ...labelStyle, marginBottom: 8 }}>GOVERNANCE & SELF-HEAL</div>
        <div style={{ fontSize: 12, color: "#64748b" }}>Loading...</div>
      </div>
    );
  }

  // Drift section
  const driftData = drift as Record<string, unknown> | null | undefined;
  const driftScore = typeof driftData?.score === "number" ? driftData.score : 0;
  const driftTrend = typeof driftData?.trend === "string" ? driftData.trend : "unknown";
  const driftColor = getDriftColor(driftScore);

  // Security section
  const securityData = security as Record<string, unknown> | null | undefined;
  const securityPassed = Boolean(securityData?.passed);
  const highSeverityTotal =
    typeof securityData?.high_severity_total === "number"
      ? securityData.high_severity_total
      : 0;

  // Tokens / Self-Heal section
  const tokensData = tokens as Record<string, unknown> | null | undefined;
  const tokenStatus = typeof tokensData?.status === "string" ? tokensData.status : "unknown";
  const suggestions = Array.isArray(tokensData?.suggestions) ? tokensData.suggestions : [];
  const queueActions = Array.isArray(tokensData?.queue_actions) ? tokensData.queue_actions : [];
  const firstSuggestion =
    suggestions.length > 0
      ? (suggestions[0] as Record<string, unknown>)
      : null;
  const firstSuggestionTitle =
    firstSuggestion && typeof firstSuggestion.title === "string"
      ? firstSuggestion.title.length > 50
        ? firstSuggestion.title.slice(0, 50) + "…"
        : firstSuggestion.title
      : null;
  const firstQueueStatus =
    queueActions.length > 0
      ? typeof (queueActions[0] as Record<string, unknown>).status === "string"
        ? (queueActions[0] as Record<string, unknown>).status as string
        : ""
      : "";
  const queueBadge = firstQueueStatus ? getQueueActionBadge(firstQueueStatus) : null;
  const tokenStatusColor = getStatusBadgeColor(tokenStatus);

  // Unified Guard section
  const guardData = unified_guard as Record<string, unknown> | null | undefined;
  const guardOk = Boolean(guardData?.ok);
  const codegraphStatus =
    typeof guardData?.codegraph_status === "string" ? guardData.codegraph_status : null;

  return (
    <div style={panelStyle}>
      {/* HEADER */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 8,
        }}
      >
        <span style={labelStyle}>GOVERNANCE & SELF-HEAL</span>
        <span
          style={{
            display: "inline-block",
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: guardOk ? "#22c55e" : "#ef4444",
            flexShrink: 0,
          }}
          title={guardOk ? "Guard OK" : "Guard FAIL"}
        />
      </div>

      {/* SECTION 1 — DRIFT */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
        <span style={sectionLabelStyle}>Drift</span>
        <span style={{ ...valueStyle, color: driftColor, fontWeight: 600 }}>
          {driftScore}
        </span>
        <span style={{ color: driftColor, fontSize: 12 }}>{driftTrend}</span>
      </div>

      <div style={separatorStyle} />

      {/* SECTION 2 — SECURITY */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
        <span style={sectionLabelStyle}>Security</span>
        <span
          style={{
            ...valueStyle,
            color: securityPassed ? "#22c55e" : "#ef4444",
            fontWeight: 600,
          }}
        >
          {securityPassed ? "CLEAN" : "FINDINGS"}
        </span>
        <span
          style={{
            fontSize: 11,
            color: highSeverityTotal > 0 ? "#ef4444" : "#64748b",
          }}
        >
          ({highSeverityTotal > 0 ? `${highSeverityTotal} high` : "0 high"})
        </span>
      </div>

      <div style={separatorStyle} />

      {/* SECTION 3 — SELF-HEAL */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
          <span style={sectionLabelStyle}>Self-Heal</span>
          <span
            style={{
              fontSize: 11,
              color: tokenStatusColor,
              fontWeight: 600,
              background: `${tokenStatusColor}22`,
              padding: "1px 6px",
              borderRadius: 4,
              border: `1px solid ${tokenStatusColor}44`,
            }}
          >
            {tokenStatus.toUpperCase()}
          </span>
        </div>
        <div style={{ marginTop: 4, paddingLeft: 78 }}>
          {firstSuggestionTitle ? (
            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" as const }}>
              <span style={{ fontSize: 11, color: "#64748b" }}>{firstSuggestionTitle}</span>
              {queueBadge && (
                <span
                  style={{
                    fontSize: 10,
                    color: queueBadge.color,
                    background: `${queueBadge.color}22`,
                    padding: "1px 5px",
                    borderRadius: 3,
                    border: `1px solid ${queueBadge.color}44`,
                    fontWeight: 600,
                  }}
                >
                  {queueBadge.label}
                </span>
              )}
            </div>
          ) : (
            <span style={{ fontSize: 11, color: "#64748b" }}>No active remediation</span>
          )}
        </div>
      </div>

      <div style={separatorStyle} />

      {/* SECTION 4 — GUARD */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
        <span style={sectionLabelStyle}>Guard</span>
        <span
          style={{
            ...valueStyle,
            color: guardOk ? "#22c55e" : "#ef4444",
            fontWeight: 600,
          }}
        >
          {guardOk ? "BOOT OK" : "BOOT FAIL"}
        </span>
        {codegraphStatus && (
          <span style={{ fontSize: 11, color: "#f59e0b99" }}>{codegraphStatus}</span>
        )}
      </div>
    </div>
  );
}
