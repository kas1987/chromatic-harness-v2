"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getMissions,
  getBeads,
  createMission,
  getMissionEvents,
  type Mission,
  type Bead,
  type MagnetEvent,
} from "@/lib/api";

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

function priorityColor(p: string) {
  return p === "p0" ? "#e53" : p === "p1" ? "#e93" : p === "p2" ? "#39e" : "#666";
}

function riskColor(delta: number) {
  return delta > 0.3 ? "#e53" : delta > 0.1 ? "#e93" : "#4a4";
}

export default function ConsolePage() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [beads, setBeads] = useState<Bead[]>([]);
  const [events, setEvents] = useState<MagnetEvent[]>([]);
  const [selected, setSelected] = useState<Mission | null>(null);
  const [newObjective, setNewObjective] = useState("");
  const [apiStatus, setApiStatus] = useState<"ok" | "err" | "?">("?");

  const refresh = useCallback(async () => {
    try {
      const [ms, bs] = await Promise.all([getMissions(), getBeads()]);
      setMissions(ms);
      setBeads(bs);
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

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: 18, color: "#ccc" }}>⬡ Chromatic Harness v2</h1>
        <span style={BADGE(apiStatus === "ok" ? "#1a7" : apiStatus === "err" ? "#e53" : "#555")}>
          API {apiStatus}
        </span>
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
              placeholder="New mission objective…"
              style={{
                flex: 1, background: "#1a1a1a", border: "1px solid #333",
                color: "#e0e0e0", padding: "4px 8px", borderRadius: 3, fontFamily: "monospace", fontSize: 12,
              }}
            />
            <button
              onClick={handleCreateMission}
              style={{
                background: "#1a4a8a", border: "none", color: "#fff",
                padding: "4px 10px", borderRadius: 3, cursor: "pointer", fontFamily: "monospace", fontSize: 12,
              }}
            >
              GO
            </button>
          </div>
          {missions.length === 0 && <p style={{ color: "#555", fontSize: 12 }}>No missions yet.</p>}
          {missions.map(m => (
            <div
              key={m.mission_id}
              onClick={() => handleSelectMission(m)}
              style={{
                padding: "6px 8px", marginBottom: 4, borderRadius: 3,
                background: selected?.mission_id === m.mission_id ? "#1a2a3a" : "#1a1a1a",
                cursor: "pointer", fontSize: 12, border: "1px solid " + (selected?.mission_id === m.mission_id ? "#39e" : "#222"),
              }}
            >
              <span style={{ color: "#39e" }}>{m.mission_id}</span>
              <span style={{ marginLeft: 8 }}>{m.objective.slice(0, 60)}</span>
              <div style={{ marginTop: 3 }}>
                <span style={{ color: "#555", fontSize: 10 }}>conf={m.confidence_required} · {m.magnets.length} magnets · {m.status}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Panel 2 — Magnet Event Stream */}
        <div style={PANEL}>
          <p style={HEADING}>
            Magnet Event Stream
            {selected && <span style={{ color: "#555", fontWeight: "normal", textTransform: "none", letterSpacing: 0 }}> — {selected.mission_id}</span>}
          </p>
          {!selected && <p style={{ color: "#555", fontSize: 12 }}>Select a mission to view events.</p>}
          {events.length === 0 && selected && <p style={{ color: "#555", fontSize: 12 }}>No events yet.</p>}
          {events.slice(-20).reverse().map(ev => (
            <div key={ev.event_id} style={{
              padding: "5px 8px", marginBottom: 3, borderRadius: 3, fontSize: 11,
              background: "#1a1a1a", borderLeft: `3px solid ${riskColor(ev.risk_delta)}`,
            }}>
              <span style={{ color: "#aaa" }}>{ev.magnet_name}</span>
              <span style={{ color: "#555", marginLeft: 6 }}>{ev.inflection_point}</span>
              {ev.risk_delta !== 0 && (
                <span style={BADGE(riskColor(ev.risk_delta))}>risk {ev.risk_delta > 0 ? "+" : ""}{ev.risk_delta.toFixed(2)}</span>
              )}
              <div style={{ color: "#444", marginTop: 2, fontSize: 10 }}>
                {new Date(ev.timestamp).toLocaleTimeString()} · {ev.recommended_action}
              </div>
            </div>
          ))}
        </div>

        {/* Panel 3 — Confidence / Risk */}
        <div style={PANEL}>
          <p style={HEADING}>Confidence & Risk</p>
          {!selected && <p style={{ color: "#555", fontSize: 12 }}>Select a mission.</p>}
          {selected && (
            <>
              <div style={{ marginBottom: 10 }}>
                <div style={{ color: "#888", fontSize: 11, marginBottom: 4 }}>Required Confidence</div>
                <div style={{ height: 12, background: "#1a1a1a", borderRadius: 6, overflow: "hidden", border: "1px solid #333" }}>
                  <div style={{
                    height: "100%", borderRadius: 6,
                    width: `${selected.confidence_required}%`,
                    background: selected.confidence_required >= 75 ? "#1a7a3a" : "#8a4a1a",
                  }} />
                </div>
                <div style={{ color: "#aaa", fontSize: 12, marginTop: 4 }}>{selected.confidence_required}%</div>
              </div>
              <div style={{ fontSize: 12, color: "#888" }}>
                <div>Autonomy: <span style={{ color: "#e0e0e0" }}>{selected.autonomy_level}</span></div>
                <div style={{ marginTop: 4 }}>Magnets: <span style={{ color: "#e0e0e0" }}>{selected.magnets.join(", ")}</span></div>
                <div style={{ marginTop: 4 }}>
                  Risk events: <span style={{ color: events.filter(e => e.risk_delta > 0.1).length > 0 ? "#e93" : "#4a4" }}>
                    {events.filter(e => e.risk_delta > 0.1).length}
                  </span>
                </div>
                {selected.stop_conditions.length > 0 && (
                  <div style={{ marginTop: 6 }}>
                    <div style={{ color: "#666", marginBottom: 2 }}>Stop conditions:</div>
                    {selected.stop_conditions.map(sc => (
                      <div key={sc} style={{ color: "#e53", fontSize: 11 }}>• {sc}</div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Panel 4 — Beads Queue */}
        <div style={PANEL}>
          <p style={HEADING}>Beads Queue ({beads.length})</p>
          {beads.length === 0 && <p style={{ color: "#555", fontSize: 12 }}>No beads yet.</p>}
          {beads.map(b => (
            <div key={b.bead_id} style={{
              padding: "6px 8px", marginBottom: 4, borderRadius: 3,
              background: "#1a1a1a", fontSize: 12, border: "1px solid #222",
            }}>
              <span style={BADGE(priorityColor(b.priority))}>{b.priority}</span>
              <span style={BADGE(b.status === "done" ? "#1a7" : b.status === "active" ? "#39e" : "#555")}>{b.status}</span>
              <span style={{ marginLeft: 8, color: "#ccc" }}>{b.title}</span>
              <div style={{ color: "#555", fontSize: 10, marginTop: 2 }}>
                {b.bead_id} · {b.source} · {new Date(b.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}
