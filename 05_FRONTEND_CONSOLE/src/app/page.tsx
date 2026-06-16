"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getMissions,
  getBeads,
  getAgents,
  createMission,
  getMissionEvents,
  synthesizeMission,
  type Mission,
  type Bead,
  type MagnetEvent,
  type AgentProfile,
  type SynthesisResult,
} from "@/lib/api";
import { useTheme } from "@/lib/theme";
import { useMode } from "@/lib/mode";
import ThemeSwitcher from "@/components/ThemeSwitcher";
import ModeSwitcher from "@/components/ModeSwitcher";
import AgentProfiles from "@/components/AgentProfiles";
import AgentRegistration from "@/components/AgentRegistration";
import useWebSocketEvents from "@/hooks/useWebSocketEvents";
import PipelineFlow from "@/components/PipelineFlow";
import MagnetsConsole from "@/components/MagnetsConsole";
import BeadsKanban from "@/components/BeadsKanban";
import ConfidenceGate from "@/components/ConfidenceGate";
import EventStream from "@/components/EventStream";
import AgentActivity from "@/components/AgentActivity";
import HarnessHealth from "@/components/HarnessHealth";
import BudgetPanel from "@/components/BudgetPanel";
import GitCI from "@/components/GitCI";
import useHarnessData from "@/hooks/useHarnessData";

const REPO = process.env.NEXT_PUBLIC_REPO || "chromatic-harness-v2";
const BRANCH = process.env.NEXT_PUBLIC_BRANCH || "main";

export default function ConsolePage() {
  const { theme } = useTheme();
  // Advisory/UI-only console mode — changes labels, hints, and emphasis only.
  // Never overrides CMP, gates, or autonomy enforcement (the runtime is authoritative).
  const { mode } = useMode();
  const { data: harnessData, loading: harnessLoading } = useHarnessData(30000);

  // Theme-derived style helpers (recomputed when the active asset pack changes).
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
    color: theme.heading,
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
  const chip: React.CSSProperties = { fontSize: 11, color: theme.muted };
  const priorityColor = (p: string) =>
    p === "p0" ? theme.danger : p === "p1" ? theme.warning : p === "p2" ? theme.info : theme.muted;
  const riskColor = (delta: number) =>
    delta > 0.3 ? theme.danger : delta > 0.1 ? theme.warning : theme.success;

  const [missions, setMissions] = useState<Mission[]>([]);
  const [beads, setBeads] = useState<Bead[]>([]);
  const [events, setEvents] = useState<MagnetEvent[]>([]);
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentProfile | null>(null);
  const [selected, setSelected] = useState<Mission | null>(null);
  const [newObjective, setNewObjective] = useState("");
  const [apiStatus, setApiStatus] = useState<"ok" | "err" | "?">("?");
  const [reviews, setReviews] = useState<SynthesisResult[]>([]);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [beadFilter, setBeadFilter] = useState<"all" | "pending" | "active" | "done">("all");
  const [beadPriorityFilter, setBeadPriorityFilter] = useState<"all" | "p0" | "p1" | "p2" | "p3">("all");

  // Clock state for the header time display
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Live magnet events for the selected mission via WebSocket (backend :8787).
  const { events: wsEvents, connected: wsLive } = useWebSocketEvents(selected?.mission_id ?? null);

  const refresh = useCallback(async () => {
    try {
      const [ms, bs, ags] = await Promise.all([getMissions(), getBeads(), getAgents()]);
      setMissions(ms);
      setBeads(bs);
      setAgents(ags);
      setApiStatus("ok");
      if (selected) {
        const evs = await getMissionEvents(selected.mission_id);
        setEvents(evs);
      }
    } catch {
      setApiStatus("err");
    }
  }, [selected]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  async function handleCreateMission() {
    // Advisory read-only guard: non-mutating modes (Auditor) cannot create missions.
    if (!mode.mutating) return;
    if (!newObjective.trim()) return;
    await createMission({ objective: newObjective, mode: mode.id });
    setNewObjective("");
    refresh();
  }

  async function handleSelectMission(m: Mission) {
    setSelected(m);
    const evs = await getMissionEvents(m.mission_id);
    setEvents(evs);
  }

  async function handleTriggerReview(createBead: boolean) {
    if (!selected) return;
    setReviewLoading(true);
    try {
      const result = await synthesizeMission(selected.mission_id, createBead);
      setReviews(prev => [result, ...prev]);
    } catch {
      // ignore
    } finally {
      setReviewLoading(false);
    }
  }

  const filteredBeads = beads.filter(b => {
    if (beadFilter !== "all" && b.status !== beadFilter) return false;
    if (beadPriorityFilter !== "all" && String(b.priority) !== beadPriorityFilter.replace("p", "")) return false;
    return true;
  });

  // Prefer live WebSocket events; fall back to the 5s-polled events when not connected.
  const displayEvents = wsLive && wsEvents.length > 0 ? wsEvents : events;

  // Derived stats for summary panels
  const completedCount = missions.filter(m => m.status === "completed").length;
  const pendingBeads = beads.filter(b => b.status === "pending").length;
  const activeBeads = beads.filter(b => b.status === "active").length;
  const doneBeads = beads.filter(b => b.status === "done").length;
  const toolPct = Math.min(displayEvents.length * 4, 100);
  const lastFail = displayEvents.filter(e => e.risk_delta > 0.2).slice(-1)[0];
  const nextAction =
    reviews[0]?.recommendation ||
    (selected ? "Awaiting Agent Lead Decision" : "Select a mission");
  const conf = reviews[0]
    ? Math.round(reviews[0].confidence_score * 100)
    : (selected?.confidence_required ?? 0);

  // Known magnet names (used for dot row in panel c)
  const knownMagnets = selected?.magnets ?? [];
  const magnetRiskMap: Record<string, number> = {};
  displayEvents.forEach(e => {
    if (!(e.magnet_name in magnetRiskMap) || magnetRiskMap[e.magnet_name] < e.risk_delta) {
      magnetRiskMap[e.magnet_name] = e.risk_delta;
    }
  });

  return (
    <div
      style={{
        maxWidth: 1600,
        margin: "0 auto",
        padding: "16px 20px",
        fontFamily: "var(--font-body, sans-serif)",
      }}
    >
      {/* ── 1. HEADER BAR ─────────────────────────────────────────────── */}
      <div
        className="cc-panel"
        style={{
          marginBottom: 14,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 8,
          padding: "10px 14px",
        }}
      >
        {/* Left group */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 24, color: "var(--cc-brand, var(--color-primary-500))", lineHeight: 1 }}>
            ⬡
          </span>
          <span
            className="chromatic-text-gradient"
            style={{ fontSize: 16, fontWeight: "bold", letterSpacing: 0.5 }}
          >
            CHROMATIC HARNESS 2.0
          </span>
          <div
            style={{
              width: 1,
              height: 20,
              background: "var(--color-border, #1e293b)",
              flexShrink: 0,
            }}
          />
          <span style={{ fontSize: 12, color: "var(--cc-muted, #475569)", maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {selected
              ? selected.objective.slice(0, 45) + (selected.objective.length > 45 ? "…" : "")
              : "No active mission"}
          </span>
        </div>

        {/* Center: mode hint */}
        <div style={{ fontSize: 10, color: "var(--cc-muted, #475569)", textAlign: "center", flex: "1 1 auto" }}>
          {mode.hint}
        </div>

        {/* Right group */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 9, fontFamily: "var(--font-mono, monospace)", color: "var(--cc-muted, #475569)" }}>
            Repo {REPO}
          </span>
          <span style={{ fontSize: 9, fontFamily: "var(--font-mono, monospace)", color: "var(--cc-muted, #475569)" }}>
            Branch {BRANCH}
          </span>
          <ModeSwitcher />
          <ThemeSwitcher />
          <span
            className={
              "chromatic-badge " +
              (apiStatus === "ok"
                ? "chromatic-badge-success"
                : apiStatus === "err"
                ? "chromatic-badge-error"
                : "")
            }
            style={{ fontSize: 10 }}
          >
            API {apiStatus}
          </span>
          <span
            style={{
              fontSize: 12,
              fontFamily: "var(--font-mono, monospace)",
              color: "var(--color-text-secondary, #94a3b8)",
            }}
          >
            {now.toLocaleTimeString()}
          </span>
          <button
            className="chromatic-button chromatic-button-primary"
            style={{ fontSize: 11, padding: "4px 12px" }}
            disabled={!mode.mutating || !selected}
            onClick={handleCreateMission}
          >
            {mode.primaryAction}
          </button>
          <button
            className="chromatic-button chromatic-button-ghost"
            style={{ fontSize: 11, padding: "4px 12px" }}
          >
            PAUSE
          </button>
          <button
            className="chromatic-button chromatic-button-ghost"
            style={{ fontSize: 11, padding: "4px 12px", color: "var(--color-error, #ef4444)" }}
          >
            STOP
          </button>
        </div>
      </div>

      {/* ── 2. TOP SUMMARY ROW ────────────────────────────────────────── */}
      <div
        className="cc-grid-top"
        style={{
          marginBottom: 14,
          display: "grid",
          gridTemplateColumns: "repeat(6, 1fr)",
          gap: 10,
        }}
      >
        {/* a. Mission Progress */}
        <div className="cc-panel cc-panel-sm" style={{ textAlign: "center" }}>
          <p className="cc-panel-title">Mission Progress</p>
          <svg viewBox="0 0 80 80" width={80} height={80} style={{ display: "block", margin: "0 auto 4px" }}>
            <circle cx={40} cy={40} r={32} fill="none" stroke="#1e293b" strokeWidth={8} />
            <circle
              cx={40}
              cy={40}
              r={32}
              fill="none"
              stroke="#8b5cf6"
              strokeWidth={8}
              strokeDasharray={`${(completedCount / Math.max(1, missions.length)) * 201.06} 201.06`}
              strokeDashoffset={50.27}
              strokeLinecap="round"
              style={{ transition: "stroke-dasharray 0.4s ease" }}
            />
            <text x={40} y={45} textAnchor="middle" fill="#f8fafc" fontSize={14} fontWeight="bold">
              {missions.length > 0 ? Math.round((completedCount / missions.length) * 100) : 0}%
            </text>
          </svg>
          <div className="cc-stat-value">{completedCount}/{missions.length}</div>
          <div className="cc-stat-label">Missions Complete</div>
        </div>

        {/* b. Beads */}
        <div className="cc-panel cc-panel-sm">
          <p className="cc-panel-title">Beads</p>
          <div style={{ display: "flex", justifyContent: "space-around", marginBottom: 6 }}>
            <div style={{ textAlign: "center" }}>
              <div className="cc-stat-value" style={{ fontSize: 22, color: "#94a3b8" }}>{pendingBeads}</div>
              <div className="cc-stat-label">New</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div className="cc-stat-value" style={{ fontSize: 22, color: "#a78bfa" }}>{activeBeads}</div>
              <div className="cc-stat-label">Active</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div className="cc-stat-value" style={{ fontSize: 22, color: "#22c55e" }}>{doneBeads}</div>
              <div className="cc-stat-label">Done</div>
            </div>
          </div>
          <div style={{ fontSize: 9, color: "var(--cc-muted, #475569)", textAlign: "right", cursor: "pointer" }}>
            View Beads →
          </div>
        </div>

        {/* c. Magnets */}
        <div className="cc-panel cc-panel-sm">
          <p className="cc-panel-title">Magnets</p>
          <div className="cc-stat-value">{selected ? selected.magnets.length : 0}/9</div>
          <div className="cc-stat-label">Reporting</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
            {knownMagnets.map(m => {
              const risk = magnetRiskMap[m] ?? 0;
              const dotColor = risk > 0.2 ? "#f59e0b" : "#22c55e";
              return (
                <span
                  key={m}
                  title={m}
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: dotColor,
                    display: "inline-block",
                  }}
                />
              );
            })}
          </div>
        </div>

        {/* d. Token Budget */}
        <div className="cc-panel cc-panel-sm">
          <p className="cc-panel-title">Token Budget</p>
          {harnessData?.health?.budget_weekly ? (() => {
            const bw = harnessData.health.budget_weekly;
            const pct = Math.round((bw.current_usd / Math.max(0.01, bw.cap_usd)) * 100);
            const over = bw.current_usd > bw.cap_usd;
            return (
              <>
                <div className="cc-stat-value" style={{ color: over ? "#ef4444" : pct > 80 ? "#f59e0b" : "#22c55e" }}>
                  ${bw.current_usd.toFixed(2)}
                </div>
                <div className="cc-stat-label">/ ${bw.cap_usd.toFixed(0)} weekly cap {over && <span style={{color:"#ef4444",fontWeight:"bold"}}> OVER</span>}</div>
                <div className="cc-progress-bar cc-progress-bar-lg" style={{ marginTop: 8 }}>
                  <div className="cc-progress-fill" style={{ width: Math.min(100, pct) + "%", background: over ? "#ef4444" : pct > 80 ? "#f59e0b" : "#22c55e" }} />
                </div>
              </>
            );
          })() : (
            <>
              <div className="cc-stat-value">{toolPct}%</div>
              <div className="cc-stat-label">Tool calls used</div>
            </>
          )}
        </div>

        {/* e. Latest Failure */}
        <div className="cc-panel cc-panel-sm">
          <p className="cc-panel-title" style={{ color: "#ef4444" }}>Latest Failure</p>
          {lastFail ? (
            <>
              <div style={{ fontSize: 10, fontWeight: "bold", color: "var(--color-error, #ef4444)", marginBottom: 2 }}>
                {lastFail.magnet_name}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--cc-muted, #475569)",
                  display: "-webkit-box",
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                  marginBottom: 4,
                }}
              >
                {lastFail.recommended_action}
              </div>
              <div style={{ fontSize: 9, color: "var(--cc-muted, #475569)", cursor: "pointer" }}>View Details →</div>
            </>
          ) : (
            <div style={{ fontSize: 11, color: "var(--color-success, #22c55e)" }}>No failures detected</div>
          )}
        </div>

        {/* f. Next Action */}
        <div className="cc-panel cc-panel-sm">
          <p className="cc-panel-title">Next Action</p>
          <div style={{ fontSize: 12, color: "var(--cc-text, #f8fafc)", lineHeight: 1.5, marginBottom: 8 }}>
            {nextAction.slice(0, 80)}
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="cc-tag cc-tag-active">Confidence: {conf}%</span>
            <button
              className="chromatic-button chromatic-button-primary"
              style={{ fontSize: 11, padding: "3px 10px" }}
              onClick={() => selected && handleTriggerReview(false)}
              disabled={!selected || reviewLoading}
            >
              Proceed →
            </button>
          </div>
        </div>
      </div>

      {/* ── 3. LIVE PIPELINE ──────────────────────────────────────────── */}
      <PipelineFlow mission={selected} events={displayEvents} />

      {/* ── 4. HARNESS STATUS ROW ─────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 14 }}>
        <HarnessHealth health={harnessData?.health ?? null} tokens={harnessData?.tokens ?? null} loading={harnessLoading} />
        <BudgetPanel health={harnessData?.health ?? null} loading={harnessLoading} />
        <GitCI git={harnessData?.git ?? null} ci={harnessData?.ci ?? null} loading={harnessLoading} />
      </div>

      {/* ── 5. MAIN SECTION ───────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 14, marginBottom: 14 }}>
        {/* Left column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <MagnetsConsole mission={selected} events={displayEvents} />
          <AgentActivity agents={agents} missions={missions} />
        </div>
        {/* Right column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <ConfidenceGate mission={selected} events={displayEvents} />
          <BeadsKanban beads={beads} />
        </div>
      </div>

      {/* ── 5. EVENT STREAM ───────────────────────────────────────────── */}
      <EventStream events={displayEvents} wsLive={wsLive} missionId={selected?.mission_id ?? null} />

      {/* ── 6. EXISTING PANELS (bottom) ───────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 14 }}>
        {/* Mission Creation */}
        <div className="cc-panel">
          <p className="cc-panel-title">Missions ({missions.length})</p>
          <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
            <input
              className="chromatic-input"
              value={newObjective}
              onChange={e => setNewObjective(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleCreateMission()}
              placeholder={mode.mutating ? "New mission objective…" : "Read-only mode — creation disabled"}
              disabled={!mode.mutating}
              style={{ flex: 1, cursor: mode.mutating ? "text" : "not-allowed" }}
            />
            <button
              className={"chromatic-button chromatic-button-primary"}
              onClick={handleCreateMission}
              disabled={!mode.mutating}
              style={{ cursor: mode.mutating ? "pointer" : "not-allowed" }}
            >
              {mode.primaryAction}
            </button>
          </div>
          {missions.length === 0 && (
            <p style={{ color: "var(--cc-muted, #475569)", fontSize: 12 }}>No missions yet.</p>
          )}
          {missions.map(m => (
            <div
              key={m.mission_id}
              onClick={() => handleSelectMission(m)}
              style={{
                padding: "6px 8px",
                marginBottom: 4,
                borderRadius: 3,
                background: theme.panelBg,
                cursor: "pointer",
                fontSize: 12,
                border:
                  "1px solid " +
                  (selected?.mission_id === m.mission_id ? theme.accent : theme.panelBorder),
              }}
            >
              <span style={{ color: theme.accent }}>{m.mission_id}</span>
              <span style={{ marginLeft: 8 }}>{m.objective.slice(0, 60)}</span>
              <div style={{ marginTop: 3 }}>
                <span style={{ color: theme.muted, fontSize: 10 }}>
                  conf={m.confidence_required} · {m.magnets.length} magnets · {m.status}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Independent Review */}
        <div className="cc-panel">
          <p className="cc-panel-title">Independent Review</p>
          {!selected && (
            <p style={{ color: theme.muted, fontSize: 12 }}>Select a mission to run a review.</p>
          )}
          {selected && (
            <>
              <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
                <button
                  className="chromatic-button chromatic-button-primary"
                  onClick={() => handleTriggerReview(false)}
                  disabled={reviewLoading}
                  style={{ fontSize: 12 }}
                >
                  {reviewLoading ? "Running…" : "Synthesize"}
                </button>
                <button
                  className="chromatic-button chromatic-button-primary"
                  onClick={() => handleTriggerReview(true)}
                  disabled={reviewLoading}
                  style={{ fontSize: 12, background: "var(--color-success, #22c55e)" }}
                >
                  + Create Bead
                </button>
              </div>
              {reviews.length === 0 && (
                <p style={{ color: theme.muted, fontSize: 12 }}>No reviews yet.</p>
              )}
              {reviews.map((r, i) => (
                <div
                  key={i}
                  style={{
                    padding: "6px 8px",
                    marginBottom: 6,
                    borderRadius: 3,
                    background: theme.panelBg,
                    fontSize: 12,
                    border: `1px solid ${theme.panelBorder}`,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", marginBottom: 4 }}>
                    <span
                      style={BADGE(
                        r.risk_level === "high"
                          ? theme.danger
                          : r.risk_level === "medium"
                          ? theme.warning
                          : theme.success
                      )}
                    >
                      {r.risk_level}
                    </span>
                    <span style={{ marginLeft: 8, color: theme.text }}>{r.recommendation}</span>
                    {r.bead_created && <span style={BADGE(theme.success)}>bead created</span>}
                  </div>
                  <div style={{ color: theme.muted, fontSize: 11 }}>
                    conf={Math.round((r.confidence_score || 0) * 100)}% · {r.summary?.slice(0, 80)}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      </div>

      {/* Agent Profiles + Registration */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 14 }}>
        <AgentProfiles
          agents={agents}
          selectedAgent={selectedAgent}
          onSelect={setSelectedAgent}
        />
        <AgentRegistration
          selectedAgent={selectedAgent}
          onAgentRegistered={(agent) => {
            setAgents(prev => {
              const idx = prev.findIndex(a => a.agent_id === agent.agent_id);
              return idx >= 0
                ? prev.map(a => (a.agent_id === agent.agent_id ? agent : a))
                : [agent, ...prev];
            });
            setSelectedAgent(agent);
          }}
        />
      </div>

    </div>
  );
}
