"use client";

interface WeeklyBudget {
  current_usd: number;
  cap_usd: number;
  remaining_usd: number;
  target_utilization_pct: number;
}

interface ChannelBudget {
  weekly_spent_usd: number;
  cap_weekly_usd: number;
  risk_level: string;
  weekly_utilization_forecast: number;
}

interface BudgetPanelProps {
  health: {
    budget_weekly: WeeklyBudget;
    budget_channels: Record<string, ChannelBudget>;
  } | null;
  loading: boolean;
}

function fmt(n: number): string {
  return n.toFixed(2);
}

function riskColor(risk: string): string {
  if (risk === "high") return "#ef4444";
  if (risk === "medium") return "#f59e0b";
  return "#22c55e";
}

function utilColor(pct: number): string {
  if (pct > 100) return "#ef4444";
  if (pct > 80) return "#f59e0b";
  return "#22c55e";
}

export default function BudgetPanel({ health, loading }: BudgetPanelProps) {
  if (loading) {
    return (
      <div className="cc-panel">
        <div className="cc-panel-title">BUDGET &amp; TOKEN BURN</div>
        <div style={{ color: "var(--cc-muted, #475569)", fontSize: "13px", padding: "12px 0" }}>
          Loading budget…
        </div>
      </div>
    );
  }

  if (!health) {
    return (
      <div className="cc-panel">
        <div className="cc-panel-title">BUDGET &amp; TOKEN BURN</div>
        <div style={{ color: "var(--cc-muted, #475569)", fontSize: "13px", padding: "12px 0" }}>
          No data
        </div>
      </div>
    );
  }

  const { budget_weekly, budget_channels } = health;
  const { current_usd, cap_usd, remaining_usd } = budget_weekly;
  const overCap = remaining_usd <= 0 || current_usd > cap_usd;
  const utilPct = cap_usd > 0 ? (current_usd / cap_usd) * 100 : 0;
  const barColor = utilColor(utilPct);

  const channels = Object.entries(budget_channels);

  return (
    <div className="cc-panel">
      <div className="cc-panel-title">BUDGET &amp; TOKEN BURN</div>

      {overCap && (
        <div
          style={{
            display: "inline-block",
            background: "#7f1d1d",
            color: "#ef4444",
            border: "1px solid #ef4444",
            borderRadius: "4px",
            fontSize: "11px",
            fontWeight: 700,
            letterSpacing: "0.08em",
            padding: "3px 10px",
            marginBottom: "12px",
          }}
        >
          OVER CAP
        </div>
      )}

      <div style={{ marginBottom: "8px" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
          <span
            style={{
              fontSize: "26px",
              fontWeight: 700,
              color: barColor,
              fontFamily: "var(--font-mono, monospace)",
              letterSpacing: "-0.02em",
            }}
          >
            ${fmt(current_usd)}
          </span>
          <span style={{ fontSize: "14px", color: "var(--cc-muted, #475569)" }}>
            / ${fmt(cap_usd)}
          </span>
        </div>
        <div
          style={{
            fontSize: "10px",
            color: "var(--cc-muted, #475569)",
            marginTop: "2px",
            marginBottom: "6px",
          }}
        >
          Remaining: ${fmt(Math.max(0, remaining_usd))}
        </div>
        <div className="cc-progress-bar cc-progress-bar-lg">
          <div
            className="cc-progress-fill"
            style={{
              background: barColor,
              width: `${Math.min(100, utilPct)}%`,
              transition: "width 0.4s ease",
            }}
          />
        </div>
        <div style={{ fontSize: "10px", color: "var(--cc-muted, #475569)", marginTop: "4px" }}>
          {utilPct.toFixed(1)}% utilized
        </div>
      </div>

      {channels.length > 0 && (
        <div
          style={{
            borderTop: "1px solid var(--color-border, #1e293b)",
            paddingTop: "10px",
            marginTop: "10px",
          }}
        >
          <div
            style={{
              fontSize: "9px",
              color: "var(--cc-muted, #475569)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              marginBottom: "8px",
            }}
          >
            Channels
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {channels.map(([name, ch]) => {
              const isPrimary = name === "claude_code";
              const chPct =
                ch.cap_weekly_usd > 0
                  ? (ch.weekly_spent_usd / ch.cap_weekly_usd) * 100
                  : 0;
              const chColor = riskColor(ch.risk_level);
              const forecast = ch.weekly_utilization_forecast;

              return (
                <div
                  key={name}
                  style={{
                    padding: isPrimary ? "6px 8px" : "4px 0",
                    borderRadius: isPrimary ? "4px" : "0",
                    border: isPrimary
                      ? "1px solid rgba(139, 92, 246, 0.4)"
                      : "none",
                    background: isPrimary
                      ? "rgba(139, 92, 246, 0.06)"
                      : "transparent",
                  }}
                >
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
                        fontSize: "11px",
                        fontFamily: "var(--font-mono, monospace)",
                        color: isPrimary
                          ? "#a78bfa"
                          : "var(--color-text-primary, #f8fafc)",
                        fontWeight: isPrimary ? 700 : 400,
                      }}
                    >
                      {name}
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <span
                        style={{
                          fontSize: "11px",
                          fontFamily: "var(--font-mono, monospace)",
                          color: "var(--color-text-primary, #f8fafc)",
                        }}
                      >
                        ${fmt(ch.weekly_spent_usd)}
                      </span>
                      <span
                        style={{
                          fontSize: "9px",
                          fontWeight: 700,
                          color: chColor,
                          background:
                            ch.risk_level === "high"
                              ? "rgba(239,68,68,0.15)"
                              : ch.risk_level === "medium"
                              ? "rgba(245,158,11,0.15)"
                              : "rgba(34,197,94,0.15)",
                          border: `1px solid ${chColor}`,
                          borderRadius: "3px",
                          padding: "1px 5px",
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                        }}
                      >
                        {ch.risk_level}
                      </span>
                    </div>
                  </div>

                  <div className="cc-progress-bar">
                    <div
                      className="cc-progress-fill"
                      style={{
                        background: chColor,
                        width: `${Math.min(100, chPct)}%`,
                        transition: "width 0.4s ease",
                      }}
                    />
                  </div>

                  {forecast > 1.0 && (
                    <div
                      style={{
                        fontSize: "9px",
                        color: "#f59e0b",
                        marginTop: "3px",
                        fontFamily: "var(--font-mono, monospace)",
                      }}
                    >
                      Forecast: {forecast.toFixed(1)}x cap
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
