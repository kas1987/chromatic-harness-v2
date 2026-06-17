"use client";
import { useState } from "react";
import { useDragResize, type CardRect } from "@/hooks/useDragResize";

export type CardStatus = "red" | "amber" | "green" | "running" | "idle";

interface StatusStyle { border: string; bg: string; glow: string; dot: string; dotClass?: string }

const STATUS: Record<CardStatus, StatusStyle> = {
  red:     { border: "rgba(239,68,68,0.55)",   bg: "rgba(239,68,68,0.06)",   glow: "0 0 28px rgba(239,68,68,0.22), 0 8px 32px rgba(0,0,0,0.4)",    dot: "#ef4444", dotClass: "animate-pulse-red" },
  amber:   { border: "rgba(245,158,11,0.50)",  bg: "rgba(245,158,11,0.055)", glow: "0 0 22px rgba(245,158,11,0.18), 0 8px 32px rgba(0,0,0,0.4)",   dot: "#f59e0b", dotClass: "animate-pulse-amber" },
  green:   { border: "rgba(34,197,94,0.38)",   bg: "rgba(34,197,94,0.04)",   glow: "0 0 18px rgba(34,197,94,0.1),  0 8px 32px rgba(0,0,0,0.35)",   dot: "#22c55e" },
  running: { border: "rgba(59,130,246,0.50)",  bg: "rgba(59,130,246,0.055)", glow: "0 0 22px rgba(59,130,246,0.18), 0 8px 32px rgba(0,0,0,0.4)",   dot: "#60a5fa", dotClass: "animate-pulse-blue" },
  idle:    { border: "rgba(124,58,237,0.14)",  bg: "transparent",            glow: "0 8px 32px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.03)", dot: "#475569" },
};

interface GridCardProps {
  id: string;
  title: string;
  icon?: string;
  status?: CardStatus;
  defaultRect: CardRect;
  children: React.ReactNode;
  headerExtra?: React.ReactNode;
  zIndex?: number;
  canvasW?: number;
}

export default function GridCard({
  id, title, icon, status = "idle", defaultRect, children, headerExtra, zIndex = 10, canvasW,
}: GridCardProps) {
  const [minimized, setMinimized] = useState(false);
  const { rect, dragProps, resizeProps, resetRect, undock } = useDragResize(id, defaultRect, canvasW);
  const s = STATUS[status];
  const dockSide = rect.dockSide;

  /* ── DOCK MODE: compact nav tab ─────────────────────────────────── */
  if (dockSide) {
    const isLeft = dockSide === "left";
    return (
      <div
        className="grid-card grid-card--docked"
        style={{
          left: isLeft ? 0 : undefined,
          right: isLeft ? undefined : 0,
          top: rect.y,
          width: 180,
          height: "auto",
          background: "linear-gradient(145deg, rgba(16,14,28,0.94) 0%, rgba(10,10,20,0.97) 100%)",
          backdropFilter: "blur(18px)",
          WebkitBackdropFilter: "blur(18px)",
          border: `1px solid ${s.border}`,
          borderLeft: isLeft  ? `3px solid ${s.dot}` : `1px solid ${s.border}`,
          borderRight: !isLeft ? `3px solid ${s.dot}` : `1px solid ${s.border}`,
          boxShadow: s.glow,
          zIndex,
          position: "absolute",
          borderRadius: isLeft ? "0 8px 8px 0" : "8px 0 0 8px",
          transition: "box-shadow 0.3s ease, border-color 0.3s ease",
        }}
      >
        <div style={{
          padding: "7px 10px",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6,
          userSelect: "none",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
            <span
              className={s.dotClass}
              style={{ width: 6, height: 6, borderRadius: "50%", background: s.dot, flexShrink: 0 }}
            />
            {icon && <span style={{ fontSize: 10 }}>{icon}</span>}
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase",
              color: "rgba(203,213,225,0.85)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }}>
              {title}
            </span>
          </div>
          <button
            className="grid-card-btn"
            onClick={() => undock()}
            title="Pop out to canvas"
            style={{ flexShrink: 0 }}
          >
            ⊙
          </button>
        </div>
      </div>
    );
  }

  /* ── NORMAL CARD ─────────────────────────────────────────────────── */
  return (
    <div
      className={`grid-card${minimized ? " grid-card--minimized" : ""}`}
      style={{
        left: rect.x,
        top: rect.y,
        width: rect.w,
        height: minimized ? "auto" : rect.h,
        background: "linear-gradient(145deg, rgba(16,14,28,0.88) 0%, rgba(10,10,20,0.92) 100%)",
        backdropFilter: "blur(18px)",
        WebkitBackdropFilter: "blur(18px)",
        border: `1px solid ${s.border}`,
        boxShadow: s.glow,
        zIndex,
        transition: "box-shadow 0.3s ease, border-color 0.3s ease",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Status tint overlay */}
      {status !== "idle" && (
        <div style={{
          position: "absolute", inset: 0, background: s.bg,
          pointerEvents: "none", borderRadius: 11, zIndex: 0,
        }} />
      )}

      {/* Header — drag handle */}
      <div
        className="grid-card__header"
        {...dragProps}
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "7px 11px",
          borderBottom: minimized ? "none" : "1px solid rgba(255,255,255,0.048)",
          cursor: "grab",
          userSelect: "none",
          background: "rgba(0,0,0,0.22)",
          borderRadius: minimized ? 11 : "11px 11px 0 0",
          position: "relative", zIndex: 2, flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span
            className={s.dotClass}
            style={{ width: 7, height: 7, borderRadius: "50%", background: s.dot, flexShrink: 0, display: "inline-block" }}
          />
          {icon && <span style={{ fontSize: 11, lineHeight: 1 }}>{icon}</span>}
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase",
            fontFamily: "var(--font-heading, Inter, sans-serif)",
            color: "rgba(203,213,225,0.9)",
          }}>
            {title}
          </span>
        </div>

        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          {headerExtra}
          <button className="grid-card-btn" onClick={(e) => { e.stopPropagation(); resetRect(); }} title="Reset position & size">↺</button>
          <button className="grid-card-btn" onClick={(e) => { e.stopPropagation(); setMinimized(m => !m); }} title={minimized ? "Expand" : "Minimize"}>
            {minimized ? "▢" : "—"}
          </button>
        </div>
      </div>

      {/* Body */}
      {!minimized && (
        <div
          className="grid-card__body hg-card-content"
          style={{ padding: "12px 14px", flex: 1, overflow: "auto", position: "relative", zIndex: 1, minHeight: 0 }}
        >
          {children}
        </div>
      )}

      {/* Resize handle */}
      {!minimized && (
        <div className="grid-card__resize" {...resizeProps}>
          <svg width={9} height={9} viewBox="0 0 9 9" fill="none">
            <line x1="8" y1="1" x2="1" y2="8" stroke="rgba(139,92,246,0.6)" strokeWidth="1.5" strokeLinecap="round" />
            <line x1="8" y1="4" x2="4" y2="8" stroke="rgba(139,92,246,0.6)" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
      )}
    </div>
  );
}
