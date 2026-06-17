"use client";

import { useState, useCallback, useEffect } from "react";
import GridCard, { type CardStatus } from "@/components/GridCard";

type RunStatus = "idle" | "running" | "ok" | "error";

interface CheckRow { name: string; status: "pass" | "warn" | "fail"; detail: string }

interface DesignSyncData {
  timestamp: string;
  health: { status: string; score: number; fails: string[]; warns: string[] };
  budget: { current: number; cap: number; gate: string };
  ci: { conclusion: string; ok: boolean };
  hooks: { high_count: number; total_count: number };
  security: { findings: number };
  beads_ready: unknown[];
  triage: { p0: string[]; p1: string[]; p2_count: number };
  route: { action: string; next: string };
}

interface AuditData {
  timestamp: string;
  overall: "pass" | "warn" | "fail";
  summary: { pass: number; warn: number; fail: number };
  checks: CheckRow[];
  registry: { nodes: number; edges: number } | null;
}

interface GenerateData {
  timestamp: string;
  ok: boolean;
  stages?: Array<{ name: string; ok: boolean; output: string }>;
  registry_present?: boolean;
  mermaid_file_count?: number;
}

/* ── SHARED MICRO-COMPONENTS ─────────────────────────────────────────── */

function SeverityBadge({ level }: { level: string }) {
  const map: Record<string, { bg: string; color: string; label: string }> = {
    pass:  { bg: "rgba(20,83,45,0.25)",   color: "#22c55e", label: "PASS" },
    ok:    { bg: "rgba(20,83,45,0.25)",   color: "#22c55e", label: "OK" },
    warn:  { bg: "rgba(120,53,15,0.25)",  color: "#f59e0b", label: "WARN" },
    fail:  { bg: "rgba(127,29,29,0.25)",  color: "#ef4444", label: "FAIL" },
    error: { bg: "rgba(127,29,29,0.25)",  color: "#ef4444", label: "ERR" },
  };
  const s = map[level] ?? { bg: "rgba(30,41,59,0.5)", color: "#94a3b8", label: level.toUpperCase() };
  return (
    <span style={{
      fontSize: 9, fontWeight: 800, padding: "2px 6px", borderRadius: 4,
      background: s.bg, color: s.color, border: `1px solid ${s.color}44`,
      letterSpacing: "0.08em", fontFamily: "var(--font-heading,Inter,sans-serif)",
    }}>
      {s.label}
    </span>
  );
}

function GateChip({ gate }: { gate: string }) {
  const color = gate === "GREEN" ? "#22c55e" : gate === "AMBER" ? "#f59e0b" : "#ef4444";
  return (
    <span style={{
      fontSize: 9, fontWeight: 800, padding: "2px 7px", borderRadius: 4,
      background: `${color}1a`, color, border: `1px solid ${color}44`,
      letterSpacing: "0.07em", fontFamily: "var(--font-heading,Inter,sans-serif)",
    }}>
      {gate}
    </span>
  );
}

function InfoBox({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{
      padding: "7px 10px", background: "rgba(0,0,0,0.28)",
      borderRadius: 7, border: "1px solid rgba(255,255,255,0.04)",
    }}>
      <div style={{ fontSize: 9, color: "#475569", marginBottom: 4, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" }}>
        {label}
      </div>
      {children}
    </div>
  );
}

function Ts({ ts }: { ts: string }) {
  return (
    <div style={{ fontSize: 9, color: "#334155", textAlign: "right", marginTop: 8 }}>
      {new Date(ts).toLocaleTimeString()}
    </div>
  );
}

/* ── DESIGN-SYNC CONTENT ─────────────────────────────────────────────── */

function DesignSyncContent({ onStatus }: { onStatus: (s: CardStatus) => void }) {
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [data, setData] = useState<DesignSyncData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(true);

  const run = useCallback(async () => {
    setRunStatus("running");
    onStatus("running");
    setError(null);
    try {
      const res = await fetch("/api/commands/design-sync");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d: DesignSyncData = await res.json();
      setData(d);
      setRunStatus("ok");
      setOpen(true);
      const severity: CardStatus =
        d.triage.p0.length > 0 ? "red" :
        d.triage.p1.length > 0 ? "amber" : "green";
      onStatus(severity);
    } catch (e) {
      setError((e as Error).message);
      setRunStatus("error");
      onStatus("red");
    }
  }, [onStatus]);

  const healthColor = (s: string) =>
    s === "green" ? "#22c55e" : s === "yellow" ? "#f59e0b" : "#ef4444";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {/* Run button row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontSize: 10, color: "#475569" }}>command center router</span>
        <div style={{ display: "flex", gap: 5 }}>
          {data && (
            <button className="grid-card-btn" style={{ width: "auto", padding: "0 8px", fontSize: 9 }}
              onClick={() => setOpen(o => !o)}>{open ? "▲ collapse" : "▼ expand"}</button>
          )}
          <button
            className="chromatic-button chromatic-button-primary"
            style={{ fontSize: 10, padding: "3px 10px" }}
            disabled={runStatus === "running"}
            onClick={run}
          >
            {runStatus === "running" ? "Scanning…" : "Run Survey"}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ fontSize: 11, color: "#ef4444", marginBottom: 8, padding: "5px 8px", background: "rgba(239,68,68,0.08)", borderRadius: 5, border: "1px solid rgba(239,68,68,0.2)" }}>
          {error}
        </div>
      )}

      {runStatus === "idle" && !data && (
        <div style={{ fontSize: 11, color: "#475569", padding: "16px 0" }}>
          Click <strong style={{ color: "#a78bfa" }}>Run Survey</strong> to scan harness state and compute triage.
        </div>
      )}

      {data && open && (
        <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
          {/* Row 1 — Health + Budget + CI */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 7 }}>
            <InfoBox label="Health">
              <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <span style={{ fontSize: 20, fontWeight: 800, color: healthColor(data.health.status), lineHeight: 1 }}>
                  {data.health.score}
                </span>
                <span style={{ fontSize: 10, color: "#475569" }}>/100</span>
                <SeverityBadge level={data.health.status === "green" ? "pass" : data.health.status === "yellow" ? "warn" : "fail"} />
              </div>
              {data.health.fails.length > 0 && (
                <div style={{ fontSize: 9, color: "#ef4444", marginTop: 3, lineHeight: 1.4 }}>
                  {data.health.fails.slice(0, 2).join(", ")}
                </div>
              )}
            </InfoBox>

            <InfoBox label="Budget">
              <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                <span style={{
                  fontSize: 14, fontWeight: 800, lineHeight: 1,
                  color: data.budget.gate === "GREEN" ? "#22c55e" : data.budget.gate === "AMBER" ? "#f59e0b" : "#ef4444",
                }}>
                  ${data.budget.current.toFixed(2)}
                </span>
                <span style={{ fontSize: 9, color: "#475569" }}>/ ${data.budget.cap}</span>
              </div>
              <div style={{ marginTop: 4 }}>
                <GateChip gate={data.budget.gate} />
              </div>
            </InfoBox>

            <InfoBox label="CI / Hooks / Sec">
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <div style={{ display: "flex", gap: 5, alignItems: "center" }}>
                  <SeverityBadge level={data.ci.ok ? "pass" : "fail"} />
                  <span style={{ fontSize: 9, color: "#475569" }}>CI</span>
                </div>
                <div style={{ fontSize: 9, color: data.hooks.high_count > 0 ? "#ef4444" : "#475569" }}>
                  hooks_high={data.hooks.high_count} total={data.hooks.total_count}
                </div>
                <div style={{ fontSize: 9, color: data.security.findings > 0 ? "#ef4444" : "#22c55e" }}>
                  sec findings={data.security.findings}
                </div>
              </div>
            </InfoBox>
          </div>

          {/* Triage */}
          <InfoBox label="Triage Matrix">
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontSize: 9, color: "#475569", letterSpacing: "0.05em" }}>P0 CRITICAL</span>
                <span style={{
                  fontSize: 20, fontWeight: 800, lineHeight: 1,
                  color: data.triage.p0.length > 0 ? "#ef4444" : "#22c55e",
                }}>
                  {data.triage.p0.length}
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontSize: 9, color: "#475569", letterSpacing: "0.05em" }}>P1 HIGH</span>
                <span style={{ fontSize: 20, fontWeight: 800, lineHeight: 1, color: data.triage.p1.length > 0 ? "#f59e0b" : "#475569" }}>
                  {data.triage.p1.length}
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontSize: 9, color: "#475569", letterSpacing: "0.05em" }}>P2 READY</span>
                <span style={{ fontSize: 20, fontWeight: 800, lineHeight: 1, color: "#22c55e" }}>
                  {data.triage.p2_count}
                </span>
              </div>
              {data.triage.p0.length > 0 && (
                <div style={{ flex: 1, fontSize: 10, color: "#f87171", padding: "4px 8px", background: "rgba(239,68,68,0.08)", borderRadius: 5, borderLeft: "2px solid #ef4444" }}>
                  {data.triage.p0[0]}
                </div>
              )}
            </div>
          </InfoBox>

          {/* Route */}
          <div style={{
            padding: "8px 11px", background: "rgba(10,8,28,0.6)", borderRadius: 7,
            borderLeft: "2px solid #8b5cf6", border: "1px solid rgba(139,92,246,0.2)",
            borderLeftWidth: 2,
          }}>
            <div style={{ fontSize: 9, color: "#475569", marginBottom: 3, letterSpacing: "0.08em", textTransform: "uppercase" }}>
              ROUTE → NEXT ACTION
            </div>
            <div style={{ fontSize: 11, color: "#c4b5fd", fontWeight: 600, marginBottom: 2 }}>{data.route.next}</div>
            <div style={{ fontSize: 10, color: "#64748b", fontFamily: "var(--font-mono,monospace)" }}>{data.route.action}</div>
          </div>

          {/* Ready beads preview */}
          {data.beads_ready.length > 0 && (
            <InfoBox label={`Ready Beads (${data.beads_ready.length})`}>
              {data.beads_ready.slice(0, 4).map((b, i) => {
                const bead = b as Record<string, unknown>;
                return (
                  <div key={i} style={{ fontSize: 10, color: "#94a3b8", padding: "2px 0", borderBottom: i < Math.min(3, data.beads_ready.length - 1) ? "1px solid rgba(255,255,255,0.04)" : "none" }}>
                    {bead.raw ? String(bead.raw) : `${bead.id ?? ""} ${bead.title ?? ""}`}
                  </div>
                );
              })}
              {data.beads_ready.length > 4 && (
                <div style={{ fontSize: 9, color: "#475569", marginTop: 3 }}>
                  +{data.beads_ready.length - 4} more · run /loop /design-sync for continuous triage
                </div>
              )}
            </InfoBox>
          )}

          <Ts ts={data.timestamp} />
        </div>
      )}
    </div>
  );
}

/* ── AUDIT-VISUAL CONTENT ────────────────────────────────────────────── */

function AuditVisualContent({ onStatus }: { onStatus: (s: CardStatus) => void }) {
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [data, setData] = useState<AuditData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(true);

  const run = useCallback(async () => {
    setRunStatus("running");
    onStatus("running");
    setError(null);
    try {
      const res = await fetch("/api/commands/audit-visual-control-plane");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d: AuditData = await res.json();
      setData(d);
      setRunStatus("ok");
      setOpen(true);
      onStatus(d.overall === "pass" ? "green" : d.overall === "warn" ? "amber" : "red");
    } catch (e) {
      setError((e as Error).message);
      setRunStatus("error");
      onStatus("red");
    }
  }, [onStatus]);

  const checkIcon = (s: "pass" | "warn" | "fail") => s === "pass" ? "✓" : s === "warn" ? "⚠" : "✗";
  const checkColor = (s: "pass" | "warn" | "fail") => s === "pass" ? "#22c55e" : s === "warn" ? "#f59e0b" : "#ef4444";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontSize: 10, color: "#475569" }}>visual control plane audit</span>
        <div style={{ display: "flex", gap: 5 }}>
          {data && (
            <button className="grid-card-btn" style={{ width: "auto", padding: "0 8px", fontSize: 9 }}
              onClick={() => setOpen(o => !o)}>{open ? "▲ collapse" : "▼ expand"}</button>
          )}
          <button
            className="chromatic-button chromatic-button-primary"
            style={{ fontSize: 10, padding: "3px 10px" }}
            disabled={runStatus === "running"}
            onClick={run}
          >
            {runStatus === "running" ? "Auditing…" : "Run Audit"}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ fontSize: 11, color: "#ef4444", marginBottom: 8, padding: "5px 8px", background: "rgba(239,68,68,0.08)", borderRadius: 5 }}>
          {error}
        </div>
      )}

      {runStatus === "idle" && !data && (
        <div style={{ fontSize: 11, color: "#475569", padding: "16px 0" }}>
          Audits CHROMATIC_TREES.md, visual_node_registry.json, Mermaid layers, and confidence gates.
        </div>
      )}

      {data && open && (
        <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
          {/* Summary header */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <SeverityBadge level={data.overall} />
            <span style={{ fontSize: 11, color: "#94a3b8" }}>
              {data.summary.pass} pass · {data.summary.warn} warn · {data.summary.fail} fail
            </span>
            {data.registry && (
              <span style={{ fontSize: 10, color: "#475569", marginLeft: "auto" }}>
                {data.registry.nodes} nodes · {data.registry.edges} edges
              </span>
            )}
          </div>

          {/* Check rows */}
          <InfoBox label="Checks">
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {data.checks.map((c, i) => (
                <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 7 }}>
                  <span style={{ color: checkColor(c.status), fontWeight: 800, flexShrink: 0, fontSize: 11, width: 12, textAlign: "center" }}>
                    {checkIcon(c.status)}
                  </span>
                  <span style={{ color: "#94a3b8", fontSize: 10, minWidth: 140, flexShrink: 0 }}>{c.name}</span>
                  <span style={{ color: "#475569", fontSize: 9, lineHeight: 1.4 }}>{c.detail}</span>
                </div>
              ))}
            </div>
          </InfoBox>

          <Ts ts={data.timestamp} />
        </div>
      )}
    </div>
  );
}

/* ── GENERATE-VISUALS CONTENT ────────────────────────────────────────── */

function GenerateVisualsContent({ onStatus }: { onStatus: (s: CardStatus) => void }) {
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [data, setData] = useState<GenerateData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load GET state on mount
  useEffect(() => {
    fetch("/api/commands/generate-visuals")
      .then(r => r.ok ? r.json() : null)
      .then((d: GenerateData | null) => {
        if (d) { setData(d); onStatus("idle"); }
      })
      .catch(() => { /* ignore */ });
  }, [onStatus]);

  const run = useCallback(async () => {
    setRunStatus("running");
    onStatus("running");
    setError(null);
    try {
      const res = await fetch("/api/commands/generate-visuals", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d: GenerateData = await res.json();
      setData(d);
      setRunStatus("ok");
      onStatus(d.ok ? "green" : "red");
    } catch (e) {
      setError((e as Error).message);
      setRunStatus("error");
      onStatus("red");
    }
  }, [onStatus]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontSize: 10, color: "#475569" }}>validate registry → generate mermaid</span>
        <button
          className="chromatic-button chromatic-button-primary"
          style={{ fontSize: 10, padding: "3px 10px" }}
          disabled={runStatus === "running"}
          onClick={run}
        >
          {runStatus === "running" ? "Generating…" : "Generate"}
        </button>
      </div>

      {error && (
        <div style={{ fontSize: 11, color: "#ef4444", marginBottom: 8, padding: "5px 8px", background: "rgba(239,68,68,0.08)", borderRadius: 5 }}>
          {error}
        </div>
      )}

      {data && (
        <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
          {/* Registry state */}
          {data.registry_present !== undefined && (
            <InfoBox label="Registry State">
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <SeverityBadge level={data.registry_present ? "pass" : "warn"} />
                <span style={{ fontSize: 10, color: "#94a3b8" }}>
                  registry {data.registry_present ? "present" : "missing"}
                </span>
                {data.mermaid_file_count !== undefined && (
                  <span style={{ fontSize: 10, color: "#475569" }}>
                    {data.mermaid_file_count} .mmd files
                  </span>
                )}
              </div>
            </InfoBox>
          )}

          {/* Stage output */}
          {data.stages && (
            <InfoBox label="Pipeline Stages">
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                {data.stages.map((s, i) => (
                  <div key={i} style={{
                    padding: "5px 8px", borderRadius: 5,
                    background: "rgba(0,0,0,0.2)",
                    borderLeft: `2px solid ${s.ok ? "#22c55e" : "#ef4444"}`,
                  }}>
                    <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: s.output ? 3 : 0 }}>
                      <SeverityBadge level={s.ok ? "pass" : "fail"} />
                      <span style={{ fontSize: 10, color: "#94a3b8" }}>{s.name}</span>
                    </div>
                    {s.output && (
                      <pre style={{ fontSize: 9, color: "#64748b", margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 60, overflow: "auto" }}>
                        {s.output.slice(0, 250)}
                      </pre>
                    )}
                  </div>
                ))}
                <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 2 }}>
                  <SeverityBadge level={data.ok ? "pass" : "fail"} />
                  <span style={{ fontSize: 10, color: "#94a3b8" }}>
                    {data.ok ? "Generation complete" : "Generation failed"}
                  </span>
                </div>
              </div>
            </InfoBox>
          )}

          <Ts ts={data.timestamp} />
        </div>
      )}

      {!data && runStatus === "idle" && (
        <div style={{ fontSize: 11, color: "#475569", padding: "16px 0" }}>
          POST runs validate_visual_registry.py → generate_harness_mermaid.py pipeline.
        </div>
      )}
    </div>
  );
}

/* ── COMMAND CENTER ROOT ─────────────────────────────────────────────── */

const DEFAULT_RECTS = {
  designSync:      { x: 0,   y: 0,   w: 500, h: 440 },
  auditVisual:     { x: 520, y: 0,   w: 440, h: 280 },
  generateVisuals: { x: 520, y: 300, w: 440, h: 200 },
};

const PANEL_LABELS: Record<string, string> = {
  designSync:      "/design-sync",
  auditVisual:     "/audit-visual",
  generateVisuals: "/generate-visuals",
};

export default function CommandCenter() {
  const [visible, setVisible] = useState<Record<string, boolean>>({
    designSync: true, auditVisual: true, generateVisuals: true,
  });
  const [statuses, setStatuses] = useState<Record<string, CardStatus>>({
    designSync: "idle", auditVisual: "idle", generateVisuals: "idle",
  });

  const setStatus = (key: string) => (s: CardStatus) =>
    setStatuses(prev => ({ ...prev, [key]: s }));

  const toggleVisible = (key: string) =>
    setVisible(prev => ({ ...prev, [key]: !prev[key] }));

  const resetAll = () => {
    Object.keys(DEFAULT_RECTS).forEach(k => {
      try { localStorage.removeItem(`grid-card-v2-cc-${k}`); } catch { /* ignore */ }
    });
    window.location.reload();
  };

  return (
    <div>
      {/* Section title */}
      <div className="cg-section-title" style={{ marginBottom: 8 }}>
        <span style={{ fontSize: 16, color: "var(--color-primary-500, #8b5cf6)", lineHeight: 1 }}>⬡</span>
        <span className="cg-section-title__label">Command Center</span>
        <div style={{ width: 1, height: 14, background: "rgba(124,58,237,0.2)", flexShrink: 0 }} />
        <span className="cg-section-title__hint">/loop /design-sync for continuous triage</span>
        <div style={{ marginLeft: "auto" }}>
          <button
            className="grid-card-btn"
            style={{ width: "auto", padding: "0 9px", fontSize: 9 }}
            onClick={resetAll}
            title="Reset all card positions"
          >
            ↺ reset layout
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="cg-filter-bar">
        <span className="cg-filter-label">Panels</span>
        {Object.keys(PANEL_LABELS).map(key => {
          const on = visible[key];
          const st = statuses[key];
          const dotColor = st === "red" ? "#ef4444" : st === "amber" ? "#f59e0b" : st === "green" ? "#22c55e" : st === "running" ? "#60a5fa" : "#475569";
          return (
            <button
              key={key}
              className={`cg-filter-chip${on ? "" : " cg-filter-chip--off"}`}
              onClick={() => toggleVisible(key)}
            >
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: dotColor, display: "inline-block", flexShrink: 0 }} />
              {PANEL_LABELS[key]}
            </button>
          );
        })}
        <span style={{ marginLeft: "auto", fontSize: 9, color: "#334155", fontFamily: "var(--font-mono,monospace)" }}>
          drag header · resize corner · — minimize
        </span>
      </div>

      {/* Grid canvas */}
      <div
        className="cg-canvas"
        style={{ minHeight: 560, width: "100%" }}
      >
        {visible.designSync && (
          <GridCard
            id="cc-designSync"
            title="/design-sync"
            icon="⬡"
            status={statuses.designSync}
            defaultRect={DEFAULT_RECTS.designSync}
            zIndex={12}
          >
            <DesignSyncContent onStatus={setStatus("designSync")} />
          </GridCard>
        )}

        {visible.auditVisual && (
          <GridCard
            id="cc-auditVisual"
            title="/audit-visual-control-plane"
            status={statuses.auditVisual}
            defaultRect={DEFAULT_RECTS.auditVisual}
            zIndex={11}
          >
            <AuditVisualContent onStatus={setStatus("auditVisual")} />
          </GridCard>
        )}

        {visible.generateVisuals && (
          <GridCard
            id="cc-generateVisuals"
            title="/generate-visuals"
            status={statuses.generateVisuals}
            defaultRect={DEFAULT_RECTS.generateVisuals}
            zIndex={10}
          >
            <GenerateVisualsContent onStatus={setStatus("generateVisuals")} />
          </GridCard>
        )}
      </div>
    </div>
  );
}
