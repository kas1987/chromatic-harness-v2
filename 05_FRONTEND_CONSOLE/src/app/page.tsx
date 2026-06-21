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
import MissionReplay from "@/components/MissionReplay";
import ClaimsCollisionDashboard from "@/components/ClaimsCollisionDashboard";
import useWebSocketEvents from "@/hooks/useWebSocketEvents";

const REPO = process.env.NEXT_PUBLIC_REPO || "chromatic-harness-v2";
const BRANCH = process.env.NEXT_PUBLIC_BRANCH || "main";

export default function ConsolePage() {
  const { theme } = useTheme();
  // Advisory/UI-only console mode — changes labels, hints, and emphasis only.
  // Never overrides CMP, gates, or autonomy enforcement (the runtime is authoritative).
  const { mode } = useMode();

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
    await createMission({ objective: newObjective });
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

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      {/* Command Center header — repo / branch / confidence + asset-pack switcher */}
      <div style={{ ...PANEL, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <h1 style={{ margin: 0, fontSize: 18, color: theme.text }}>⬡ Chromatic Harness v2</h1>
          <span style={{ fontSize: 11, color: theme.muted, textTransform: "uppercase", letterSpacing: 1 }}>Command Center</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <span style={chip}>Repo <b style={{ color: theme.text }}>{REPO}</b></span>
          <span style={chip}>Branch <b style={{ color: theme.text }}>{BRANCH}</b></span>
          <span style={chip}>Confidence <b style={{ color: theme.accent }}>{selected ? `${selected.confidence_required}%` : "—"}</b></span>
          <ModeSwitcher />
          <ThemeSwitcher />
          <span style={BADGE(apiStatus === "ok" ? theme.success : apiStatus === "err" ? theme.danger : theme.muted)}>
            API {apiStatus}
          </span>
        </div>
      </div>

      {/* Advisory mode banner — UI-only hint; does not override CMP/gates. */}
      <div style={{ color: theme.muted, fontSize: 11, marginTop: -8, marginBottom: 16 }}>
        {mode.hint + " · autonomy " + mode.autonomyBand}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

        {/* Panel 1 — Mission Dashboard */}
        <div style={PANEL}>
          <p style={HEADING}>Missions ({missions.length})</p>
          <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
            <input
              value={newObjective}
              onChange={e => setNewObjective(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleCreateMission()}
              placeholder={mode.mutating ? "New mission objective…" : "Read-only mode — creation disabled"}
              disabled={!mode.mutating}
              style={{
                flex: 1, background: theme.panelBg,
                border: `1px solid ${mode.mutating ? theme.panelBorder : theme.panelBorder}`,
                color: mode.mutating ? theme.text : theme.muted,
                padding: "4px 8px", borderRadius: 3, fontFamily: "monospace", fontSize: 12,
                cursor: mode.mutating ? "text" : "not-allowed",
              }}
            />
            <button
              onClick={handleCreateMission}
              disabled={!mode.mutating}
              style={{
                background: mode.mutating ? theme.accent : theme.panelBorder, border: "none",
                color: mode.mutating ? "#fff" : theme.muted,
                padding: "4px 10px", borderRadius: 3,
                cursor: mode.mutating ? "pointer" : "not-allowed",
                fontFamily: "monospace", fontSize: 12,
              }}
            >
              {mode.primaryAction}
            </button>
          </div>
          {missions.length === 0 && <p style={{ color: theme.muted, fontSize: 12 }}>No missions yet.</p>}
          {missions.map(m => (
            <div
              key={m.mission_id}
              onClick={() => handleSelectMission(m)}
              style={{
                padding: "6px 8px", marginBottom: 4, borderRadius: 3,
                background: theme.panelBg,
                cursor: "pointer", fontSize: 12, border: "1px solid " + (selected?.mission_id === m.mission_id ? theme.accent : theme.panelBorder),
              }}
            >
              <span style={{ color: theme.accent }}>{m.mission_id}</span>
              <span style={{ marginLeft: 8 }}>{m.objective.slice(0, 60)}</span>
              <div style={{ marginTop: 3 }}>
                <span style={{ color: theme.muted, fontSize: 10 }}>conf={m.confidence_required} · {m.magnets.length} magnets · {m.status}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Panel 2 — Magnet Event Stream */}
        <div style={PANEL}>
          <p style={HEADING}>
            Magnet Event Stream
            {selected && <span style={{ color: theme.muted, fontWeight: "normal", textTransform: "none", letterSpacing: 0 }}> — {selected.mission_id}</span>}
            {selected && (
              <span style={{ marginLeft: 8, fontSize: 10, fontWeight: "normal", letterSpacing: 0, textTransform: "none", color: wsLive ? theme.success : theme.muted }}>
                {wsLive ? "● live" : "○ polling"}
              </span>
            )}
          </p>
          {!selected && <p style={{ color: theme.muted, fontSize: 12 }}>Select a mission to view events.</p>}
          {displayEvents.length === 0 && selected && <p style={{ color: theme.muted, fontSize: 12 }}>No events yet.</p>}
          {displayEvents.slice(-20).reverse().map(ev => (
            <div key={ev.event_id} style={{
              padding: "5px 8px", marginBottom: 3, borderRadius: 3, fontSize: 11,
              background: theme.panelBg, borderLeft: `3px solid ${riskColor(ev.risk_delta)}`,
            }}>
              <span style={{ color: theme.text }}>{ev.magnet_name}</span>
              <span style={{ color: theme.muted, marginLeft: 6 }}>{ev.inflection_point}</span>
              {ev.risk_delta !== 0 && (
                <span style={BADGE(riskColor(ev.risk_delta))}>risk {ev.risk_delta > 0 ? "+" : ""}{ev.risk_delta.toFixed(2)}</span>
              )}
              <div style={{ color: theme.muted, marginTop: 2, fontSize: 10 }}>
                {new Date(ev.timestamp).toLocaleTimeString()} · {ev.recommended_action}
              </div>
            </div>
          ))}
        </div>

        {/* Panel 3 — Confidence / Risk */}
        <div style={PANEL}>
          <p style={HEADING}>Confidence & Risk</p>
          {!selected && <p style={{ color: theme.muted, fontSize: 12 }}>Select a mission.</p>}
          {selected && (
            <>
              <div style={{ marginBottom: 10 }}>
                <div style={{ color: theme.muted, fontSize: 11, marginBottom: 4 }}>Required Confidence</div>
                <div style={{ height: 12, background: theme.panelBg, borderRadius: 6, overflow: "hidden", border: `1px solid ${theme.panelBorder}` }}>
                  <div style={{
                    height: "100%", borderRadius: 6,
                    width: `${selected.confidence_required}%`,
                    background: selected.confidence_required >= 75 ? theme.success : theme.warning,
                  }} />
                </div>
                <div style={{ color: theme.text, fontSize: 12, marginTop: 4 }}>{selected.confidence_required}%</div>
              </div>
              <div style={{ fontSize: 12, color: theme.muted }}>
                <div>Autonomy: <span style={{ color: theme.text }}>{selected.autonomy_level}</span></div>
                <div style={{ marginTop: 4 }}>Magnets: <span style={{ color: theme.text }}>{selected.magnets.join(", ")}</span></div>
                <div style={{ marginTop: 4 }}>
                  Risk events: <span style={{ color: displayEvents.filter(e => e.risk_delta > 0.1).length > 0 ? theme.warning : theme.success }}>
                    {displayEvents.filter(e => e.risk_delta > 0.1).length}
                  </span>
                </div>
                {selected.stop_conditions.length > 0 && (
                  <div style={{ marginTop: 6 }}>
                    <div style={{ color: theme.muted, marginBottom: 2 }}>Stop conditions:</div>
                    {selected.stop_conditions.map(sc => (
                      <div key={sc} style={{ color: theme.danger, fontSize: 11 }}>• {sc}</div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Panel 4 — Beads Queue */}
        <div style={PANEL}>
          <p style={HEADING}>Beads Queue ({filteredBeads.length}/{beads.length})</p>
          <div style={{ display: "flex", gap: 4, marginBottom: 8, flexWrap: "wrap" }}>
            {(["all", "pending", "active", "done"] as const).map(f => (
              <button key={f} onClick={() => setBeadFilter(f)} style={{
                background: beadFilter === f ? theme.accent : theme.panelBg,
                border: `1px solid ${theme.panelBorder}`, color: theme.text, padding: "2px 7px",
                borderRadius: 3, cursor: "pointer", fontSize: 11,
              }}>{f}</button>
            ))}
            <span style={{ color: theme.muted, fontSize: 11, alignSelf: "center", marginLeft: 4 }}>|</span>
            {(["all", "p0", "p1", "p2", "p3"] as const).map(f => (
              <button key={f} onClick={() => setBeadPriorityFilter(f)} style={{
                background: beadPriorityFilter === f ? (f === "all" ? theme.accent : priorityColor(f)) : theme.panelBg,
                border: `1px solid ${theme.panelBorder}`, color: theme.text, padding: "2px 7px",
                borderRadius: 3, cursor: "pointer", fontSize: 11,
              }}>{f}</button>
            ))}
          </div>
          {filteredBeads.length === 0 && <p style={{ color: theme.muted, fontSize: 12 }}>No beads match filters.</p>}
          {filteredBeads.map(b => (
            <div key={b.bead_id} style={{
              padding: "6px 8px", marginBottom: 4, borderRadius: 3,
              background: theme.panelBg, fontSize: 12, border: `1px solid ${theme.panelBorder}`,
            }}>
              <span style={BADGE(priorityColor(b.priority))}>{b.priority}</span>
              <span style={BADGE(b.status === "done" ? theme.success : b.status === "active" ? theme.info : theme.muted)}>{b.status}</span>
              <span style={{ marginLeft: 8, color: theme.text }}>{b.title}</span>
              <div style={{ color: theme.muted, fontSize: 10, marginTop: 2 }}>
                {b.bead_id} · {b.source} · {new Date(b.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>

      </div>

      {/* Second row — Independent Review + PDR Generator */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>

        {/* Panel 5 — Independent Review Panel */}
        <div style={PANEL}>
          <p style={HEADING}>Independent Review</p>
          {!selected && <p style={{ color: theme.muted, fontSize: 12 }}>Select a mission to run a review.</p>}
          {selected && (
            <>
              <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
                <button
                  onClick={() => handleTriggerReview(false)}
                  disabled={reviewLoading}
                  style={{
                    background: reviewLoading ? theme.panelBorder : theme.accent, border: "none", color: "#fff",
                    padding: "4px 10px", borderRadius: 3, cursor: reviewLoading ? "default" : "pointer",
                    fontFamily: "monospace", fontSize: 12,
                  }}
                >
                  {reviewLoading ? "Running…" : "Synthesize"}
                </button>
                <button
                  onClick={() => handleTriggerReview(true)}
                  disabled={reviewLoading}
                  style={{
                    background: reviewLoading ? theme.panelBorder : theme.success, border: "none", color: "#fff",
                    padding: "4px 10px", borderRadius: 3, cursor: reviewLoading ? "default" : "pointer",
                    fontFamily: "monospace", fontSize: 12,
                  }}
                >
                  + Create Bead
                </button>
              </div>
              {reviews.length === 0 && <p style={{ color: theme.muted, fontSize: 12 }}>No reviews yet.</p>}
              {reviews.map((r, i) => (
                <div key={i} style={{
                  padding: "6px 8px", marginBottom: 6, borderRadius: 3,
                  background: theme.panelBg, fontSize: 12, border: `1px solid ${theme.panelBorder}`,
                }}>
                  <div style={{ display: "flex", alignItems: "center", marginBottom: 4 }}>
                    <span style={BADGE(r.risk_level === "high" ? theme.danger : r.risk_level === "medium" ? theme.warning : theme.success)}>
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

        {/* Panel 6 — PDR Generator (stub) */}
        <div style={PANEL}>
          <p style={HEADING}>PDR Generator</p>
          <p style={{ color: theme.muted, fontSize: 12, marginBottom: 8 }}>
            Generate Product Decision Records from mission data.
          </p>
          <div style={{ color: theme.muted, fontSize: 11, lineHeight: 1.6 }}>
            <div>• <span style={{ color: theme.accent }}>PDR_FRONTEND_CONSOLE.md</span> — frontend gaps</div>
            <div>• <span style={{ color: theme.accent }}>PDR_VISUAL_CONTROL_PLANE.md</span> — visual nodes</div>
            <div>• <span style={{ color: theme.accent }}>PDR_AGENT_TRUST.md</span> — agent autonomy model</div>
          </div>
          <div style={{
            marginTop: 12, padding: "6px 8px", borderRadius: 3,
            background: theme.panelBg, border: `1px solid ${theme.panelBorder}`,
            color: theme.muted, fontSize: 11, fontStyle: "italic",
          }}>
            PDR auto-generation from mission events — coming soon
          </div>
        </div>

      </div>

      {/* Third row — Action Launcher + Sandbox Lab Results */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>

        {/* Panel 7 — Action Launcher (stub) */}
        <div style={PANEL}>
          <p style={HEADING}>Action Launcher</p>
          <p style={{ color: theme.muted, fontSize: 12, marginBottom: 10 }}>Quick actions for the selected mission.</p>
          {(
            [
              { label: "Rerun Validation", desc: "Re-execute all mission gate checks", color: theme.accent },
              { label: "Create Bead", desc: "Open a new bead linked to this mission", color: theme.brand },
              { label: "Dispatch Agent", desc: "Assign an agent to a pending action", color: theme.success },
            ] as Array<{ label: string; desc: string; color: string }>
          ).map(action => (
            <div key={action.label} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "7px 10px", marginBottom: 6, borderRadius: 3,
              background: theme.panelBg, border: `1px solid ${theme.panelBorder}`,
            }}>
              <div>
                <div style={{ color: theme.text, fontSize: 12 }}>{action.label}</div>
                <div style={{ color: theme.muted, fontSize: 10, marginTop: 2 }}>{action.desc}</div>
              </div>
              <button style={{
                background: selected && mode.mutating ? action.color : theme.panelBorder,
                border: "none", color: selected && mode.mutating ? "#fff" : theme.muted,
                padding: "3px 10px", borderRadius: 3,
                cursor: selected && mode.mutating ? "pointer" : "not-allowed", fontSize: 11,
              }}
                disabled={!selected || !mode.mutating}
              >
                Run
              </button>
            </div>
          ))}
          {!selected && <p style={{ color: theme.muted, fontSize: 11, marginTop: 4 }}>Select a mission to enable actions.</p>}
        </div>

        {/* Panel 8 — Sandbox Lab Results (stub) */}
        <div style={PANEL}>
          <p style={HEADING}>Sandbox Lab Results</p>
          <div style={{
            padding: "20px 12px", borderRadius: 3, background: theme.panelBg,
            border: `1px solid ${theme.panelBorder}`, textAlign: "center",
          }}>
            <div style={{ color: theme.muted, fontSize: 28, marginBottom: 8 }}>⬡</div>
            <div style={{ color: theme.muted, fontSize: 12 }}>No sandbox results</div>
            <div style={{ color: theme.muted, fontSize: 11, marginTop: 4 }}>
              Sandbox lab execution is not yet active for this session.
            </div>
          </div>
        </div>

      </div>

      {/* Full-width row: Mission Replay (when mission selected) */}
      {selected && (
        <div style={{ marginTop: 16 }}>
          <MissionReplay missionId={selected.mission_id} />
        </div>
      )}

      {/* Full-width row: Agent Trust Profiles + Registration */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
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
                ? prev.map(a => a.agent_id === agent.agent_id ? agent : a)
                : [agent, ...prev];
            });
            setSelectedAgent(agent);
          }}
        />
      </div>

      {/* Full-width row: Collision Claims Dashboard */}
      <div style={{ marginTop: 16 }}>
        <ClaimsCollisionDashboard />
      </div>
    </div>
  );
}
