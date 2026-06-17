"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  getMissionAnalytics,
  getMissionEventsRange,
  type MissionAnalytics,
  type MagnetEvent,
  type TrendPoint,
} from "@/lib/api";
import { useTheme, type ConsoleTheme } from "@/lib/theme";

function Sparkline({
  points,
  color,
  height = 40,
  theme,
}: {
  points: TrendPoint[];
  color: string;
  height?: number;
  theme: ConsoleTheme;
}) {
  if (points.length < 2)
    return (
      <div style={{ height, color: theme.panelBorder, fontSize: 11 }}>—</div>
    );

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 200;
  const h = height;
  const step = w / (points.length - 1);

  const pts = points
    .map((p, i) => {
      const x = i * step;
      const y = h - ((p.value - min) / range) * (h - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}

function EventRow({
  ev,
  highlight,
  theme,
}: {
  ev: MagnetEvent;
  highlight: boolean;
  theme: ConsoleTheme;
}) {
  const riskColor =
    ev.risk_delta > 0.1
      ? theme.danger
      : ev.risk_delta < -0.05
      ? theme.success
      : theme.muted;
  return (
    <div
      style={{
        fontSize: 11,
        padding: "3px 0",
        borderBottom: `1px solid ${theme.panelBg}`,
        background: highlight ? theme.panelBorder : "transparent",
        display: "flex",
        gap: 8,
        alignItems: "center",
      }}
    >
      <span style={{ color: theme.muted, minWidth: 60 }}>
        {ev.timestamp.slice(11, 19)}
      </span>
      <span style={{ color: theme.accent, minWidth: 90 }}>{ev.magnet_name}</span>
      <span style={{ color: riskColor, minWidth: 40 }}>
        {ev.risk_delta > 0 ? "+" : ""}
        {ev.risk_delta.toFixed(2)}
      </span>
      <span style={{ color: theme.text, flex: 1 }}>{ev.recommended_action}</span>
    </div>
  );
}

interface Props {
  missionId: string;
}

export default function MissionReplay({ missionId }: Props) {
  const { theme } = useTheme();

  const PANEL: React.CSSProperties = {
    border: `1px solid ${theme.panelBorder}`,
    borderRadius: 4,
    padding: 12,
    background: theme.panelBg,
    marginBottom: 8,
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

  const [analytics, setAnalytics] = useState<MissionAnalytics | null>(null);
  const [events, setEvents] = useState<MagnetEvent[]>([]);
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const [a, evs] = await Promise.all([
      getMissionAnalytics(missionId),
      getMissionEventsRange(missionId),
    ]);
    setAnalytics(a);
    setEvents(evs);
    setPlayhead(0);
    setLoading(false);
  }, [missionId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (playing && events.length > 0) {
      intervalRef.current = setInterval(() => {
        setPlayhead((p) => {
          if (p >= events.length - 1) {
            setPlaying(false);
            return events.length - 1;
          }
          return p + 1;
        });
      }, Math.max(50, 800 / speed));
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [playing, speed, events.length]);

  if (loading) {
    return (
      <div style={PANEL}>
        <p style={HEADING}>Mission Replay</p>
        <p style={{ color: theme.muted, fontSize: 12 }}>Loading…</p>
      </div>
    );
  }

  if (!analytics || analytics.event_count === 0) {
    return (
      <div style={PANEL}>
        <p style={HEADING}>Mission Replay</p>
        <p style={{ color: theme.muted, fontSize: 12 }}>
          No events recorded for this mission.
        </p>
      </div>
    );
  }

  const visibleEvents = events.slice(0, playhead + 1);

  const btnStyle: React.CSSProperties = {
    background: theme.panelBorder,
    border: `1px solid ${theme.muted}`,
    color: theme.text,
    padding: "2px 8px",
    cursor: "pointer",
    borderRadius: 3,
    fontSize: 11,
  };

  return (
    <div style={PANEL}>
      <p style={HEADING}>
        Mission Replay — {missionId}{" "}
        <span style={{ color: theme.muted, fontWeight: "normal" }}>
          ({analytics.event_count} events · {analytics.duration_seconds}s)
        </span>
      </p>

      {/* Trend charts */}
      <div style={{ display: "flex", gap: 24, marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 10, color: theme.muted, marginBottom: 2 }}>
            Confidence Δ (cumulative)
          </div>
          <Sparkline
            points={analytics.confidence_trend}
            color={theme.accent}
            theme={theme}
          />
        </div>
        <div>
          <div style={{ fontSize: 10, color: theme.muted, marginBottom: 2 }}>
            Risk Δ (cumulative)
          </div>
          <Sparkline
            points={analytics.risk_trend}
            color={theme.warning}
            theme={theme}
          />
        </div>
        <div style={{ minWidth: 120 }}>
          <div style={{ fontSize: 10, color: theme.muted, marginBottom: 4 }}>
            Magnets
          </div>
          {analytics.magnet_breakdown.slice(0, 4).map((m) => (
            <div
              key={m.magnet_name}
              style={{ fontSize: 10, color: theme.text, marginBottom: 2 }}
            >
              <span style={{ color: theme.accent }}>{m.magnet_name}</span>{" "}
              {m.event_count}×
            </div>
          ))}
        </div>
      </div>

      {/* Playback controls */}
      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <button onClick={() => setPlayhead(0)} style={btnStyle}>
          ⏮
        </button>
        <button onClick={() => setPlaying((p) => !p)} style={btnStyle}>
          {playing ? "⏸" : "▶"}
        </button>
        <button onClick={() => setPlayhead(events.length - 1)} style={btnStyle}>
          ⏭
        </button>
        <select
          value={speed}
          onChange={(e) => setSpeed(Number(e.target.value))}
          style={{
            background: theme.panelBorder,
            border: `1px solid ${theme.muted}`,
            color: theme.text,
            padding: "2px 4px",
            borderRadius: 3,
            fontSize: 11,
          }}
        >
          <option value={0.5}>0.5×</option>
          <option value={1}>1×</option>
          <option value={2}>2×</option>
          <option value={4}>4×</option>
        </select>
        <input
          type="range"
          min={0}
          max={events.length - 1}
          value={playhead}
          onChange={(e) => {
            setPlaying(false);
            setPlayhead(Number(e.target.value));
          }}
          style={{ flex: 1 }}
        />
        <span style={{ fontSize: 11, color: theme.muted, minWidth: 60 }}>
          {playhead + 1} / {events.length}
        </span>
      </div>

      {/* Event log */}
      <div
        style={{ maxHeight: 160, overflowY: "auto", fontFamily: "monospace" }}
      >
        {visibleEvents.map((ev, i) => (
          <EventRow
            key={ev.event_id}
            ev={ev}
            highlight={i === playhead}
            theme={theme}
          />
        ))}
      </div>
    </div>
  );
}
