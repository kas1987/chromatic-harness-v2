"use client";

interface HarnessHealthProps {
  health: {
    overall_status: "green" | "yellow" | "red";
    readiness_score: number;
    counts: { pass: number; warn: number; fail: number };
    checks: Array<{ name: string; status: string; message: string }>;
  } | null;
  tokens: { status: string; counts: { pass: number; warn: number; fail: number } } | null;
  loading: boolean;
}

const statusColor: Record<string, string> = {
  green: "var(--color-success)",
  yellow: "var(--color-warning)",
  warn: "var(--color-warning)",
  red: "var(--color-error)",
  fail: "var(--color-error)",
};

function resolveColor(s: string): string {
  return statusColor[s] ?? "var(--cc-text)";
}

export default function HarnessHealth({ health, tokens, loading }: HarnessHealthProps) {
  if (loading) {
    return (
      <div className="cc-panel">
        <div className="cc-panel-title">HARNESS HEALTH</div>
        <div style={{ color: "var(--cc-muted)", fontSize: "0.8rem", padding: "8px 0" }}>
          Loading health data…
        </div>
      </div>
    );
  }

  const problemChecks = health
    ? health.checks.filter((c) => c.status === "warn" || c.status === "fail")
    : [];

  return (
    <div className="cc-panel">
      <div className="cc-panel-title">HARNESS HEALTH</div>

      <div style={{ display: "flex", gap: "16px", alignItems: "flex-start", marginBottom: "10px" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
          <div
            style={{
              background: health ? resolveColor(health.overall_status) : "var(--cc-muted)",
              color: "#000",
              fontWeight: 700,
              fontSize: "0.7rem",
              letterSpacing: "0.08em",
              padding: "4px 10px",
              borderRadius: "4px",
              minWidth: "56px",
              textAlign: "center",
            }}
          >
            {health ? health.overall_status.toUpperCase() : "—"}
          </div>
          <div style={{ color: "var(--cc-muted)", fontSize: "0.72rem" }}>
            {health ? `${health.readiness_score}/20` : "—/20"}
          </div>
        </div>

        <div style={{ display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap", flex: 1 }}>
          {(["pass", "warn", "fail"] as const).map((key) => {
            const colorMap = { pass: "var(--color-success)", warn: "var(--color-warning)", fail: "var(--color-error)" };
            return (
              <div
                key={key}
                style={{
                  border: `1px solid ${colorMap[key]}`,
                  borderRadius: "4px",
                  padding: "3px 8px",
                  fontSize: "0.72rem",
                  color: colorMap[key],
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  minWidth: "36px",
                }}
              >
                <span style={{ fontWeight: 700, fontSize: "0.85rem" }}>
                  {health ? health.counts[key] : 0}
                </span>
                <span style={{ fontSize: "0.62rem", opacity: 0.75, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  {key}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "10px", fontSize: "0.72rem" }}>
        <span style={{ color: "var(--cc-muted)", textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "0.65rem" }}>
          TOKEN GOV
        </span>
        <span
          style={{
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            background: tokens ? resolveColor(tokens.status) : "var(--cc-muted)",
            flexShrink: 0,
          }}
        />
        <span style={{ color: tokens ? resolveColor(tokens.status) : "var(--cc-muted)" }}>
          {tokens ? tokens.status : "—"}
        </span>
      </div>

      <div style={{ maxHeight: "120px", overflowY: "auto" }}>
        {problemChecks.length === 0 ? (
          <div style={{ color: "var(--color-success)", fontSize: "0.75rem" }}>All systems nominal</div>
        ) : (
          problemChecks.map((check, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "3px 0",
                borderBottom: "1px solid rgba(255,255,255,0.04)",
              }}
            >
              <span
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  background: resolveColor(check.status),
                  flexShrink: 0,
                }}
              />
              <span
                className="cc-mono cc-ellipsis"
                style={{ flex: 1, fontSize: "0.72rem", color: "var(--cc-text)", minWidth: 0 }}
              >
                {check.name}
              </span>
              <span
                style={{
                  fontSize: "0.62rem",
                  color: resolveColor(check.status),
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  flexShrink: 0,
                }}
              >
                {check.status}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
