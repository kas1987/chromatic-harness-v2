"use client";
import { useState, useRef, useEffect } from "react";
import GridCard, { type CardStatus } from "@/components/GridCard";
import type { CardRect } from "@/hooks/useDragResize";

export interface PanelDef {
  label: string;
  icon?: string;
  status?: CardStatus;
  defaultRect: CardRect;
  content: React.ReactNode;
}

interface HarnessGridProps {
  panels: Record<string, PanelDef>;
  title?: string;
  hint?: string;
  storagePrefix?: string;
  minHeight?: number;
}

export default function HarnessGrid({
  panels,
  title = "Harness Operations Grid",
  hint = "drag header · resize corner · — minimize · snap edge to dock",
  storagePrefix = "hg",
  minHeight = 1020,
}: HarnessGridProps) {
  const panelKeys = Object.keys(panels);

  const [visible, setVisible] = useState<Record<string, boolean>>(
    () => Object.fromEntries(panelKeys.map(k => [k, true]))
  );

  const canvasRef = useRef<HTMLDivElement>(null);
  const [canvasW, setCanvasW] = useState(1000);

  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      const w = entries[0]?.contentRect.width;
      if (w && w > 0) setCanvasW(w);
    });
    ro.observe(el);
    // Capture initial width immediately
    setCanvasW(el.getBoundingClientRect().width || 1000);
    return () => ro.disconnect();
  }, []);

  const toggleVisible = (key: string) =>
    setVisible(prev => ({ ...prev, [key]: !prev[key] }));

  const resetAll = () => {
    panelKeys.forEach(k => {
      try { localStorage.removeItem(`grid-card-v2-${storagePrefix}-${k}`); } catch { /* ignore */ }
    });
    window.location.reload();
  };

  return (
    <div style={{ marginBottom: 14 }}>
      {/* Section title bar */}
      <div className="cg-section-title" style={{ marginBottom: 8 }}>
        <span style={{ fontSize: 15, color: "var(--color-primary-500, #8b5cf6)", lineHeight: 1 }}>⬡</span>
        <span className="cg-section-title__label">{title}</span>
        <div style={{ width: 1, height: 14, background: "rgba(124,58,237,0.2)", flexShrink: 0 }} />
        <span className="cg-section-title__hint">{hint}</span>
        <div style={{ marginLeft: "auto" }}>
          <button
            className="grid-card-btn"
            style={{ width: "auto", padding: "0 9px", fontSize: 9 }}
            onClick={resetAll}
            title="Reset all card positions in this grid"
          >
            ↺ reset layout
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="cg-filter-bar">
        <span className="cg-filter-label">Panels</span>
        {panelKeys.map(key => {
          const p = panels[key];
          const on = visible[key];
          const st = p.status ?? "idle";
          const dotColor =
            st === "red"     ? "#ef4444" :
            st === "amber"   ? "#f59e0b" :
            st === "green"   ? "#22c55e" :
            st === "running" ? "#60a5fa" : "#475569";
          return (
            <button
              key={key}
              className={`cg-filter-chip${on ? "" : " cg-filter-chip--off"}`}
              onClick={() => toggleVisible(key)}
              title={on ? `Hide ${p.label}` : `Show ${p.label}`}
            >
              <span style={{
                width: 5, height: 5, borderRadius: "50%",
                background: dotColor, display: "inline-block", flexShrink: 0,
              }} />
              {p.label}
            </button>
          );
        })}
        <span style={{ marginLeft: "auto", fontSize: 9, color: "#334155", fontFamily: "var(--font-mono,monospace)" }}>
          ← → snap to nav rails
        </span>
      </div>

      {/* Grid canvas */}
      <div
        ref={canvasRef}
        className="cg-canvas"
        style={{ minHeight, width: "100%", position: "relative" }}
      >
        {panelKeys.map((key, idx) => {
          if (!visible[key]) return null;
          const p = panels[key];
          return (
            <GridCard
              key={key}
              id={`${storagePrefix}-${key}`}
              title={p.label}
              icon={p.icon}
              status={p.status ?? "idle"}
              defaultRect={p.defaultRect}
              zIndex={10 + (panelKeys.length - idx)}
              canvasW={canvasW}
            >
              {p.content}
            </GridCard>
          );
        })}
      </div>
    </div>
  );
}
