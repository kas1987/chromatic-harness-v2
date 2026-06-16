"use client";

import React, { useState } from "react";

interface Bead {
  bead_id: string;
  mission_id?: string;
  type: "action" | "alert" | "learning" | "score";
  title: string;
  source: string;
  priority: "p0" | "p1" | "p2" | "p3";
  status: "pending" | "active" | "done";
  severity?: "critical" | "high" | "medium" | "low";
  created_at: string;
  updated_at: string;
}

interface BeadsKanbanProps {
  beads: Bead[];
  onBeadClick?: (bead: Bead) => void;
}

const COLS = [
  { id: "new", label: "NEW", color: "#64748b", countColor: "#94a3b8" },
  { id: "ready", label: "READY", color: "#3b82f6", countColor: "#60a5fa" },
  { id: "active", label: "ACTIVE", color: "#8b5cf6", countColor: "#a78bfa" },
  { id: "review", label: "REVIEW", color: "#f59e0b", countColor: "#fbbf24" },
  { id: "blocked", label: "BLOCKED", color: "#ef4444", countColor: "#f87171" },
  { id: "done", label: "DONE", color: "#22c55e", countColor: "#4ade80" },
];

function col(b: Bead): string {
  if (b.status === "done") return "done";
  if (b.status === "active") return "active";
  if (b.type === "alert" && (b.severity === "critical" || b.severity === "high"))
    return "blocked";
  if (b.type === "alert") return "review";
  if (b.priority === "p0" || b.priority === "p1") return "ready";
  return "new";
}

const TYPE_BADGE_STYLE: Record<string, React.CSSProperties> = {
  action: {
    backgroundColor: "rgba(59,130,246,0.2)",
    color: "#60a5fa",
    border: "1px solid rgba(59,130,246,0.3)",
  },
  alert: {
    backgroundColor: "rgba(239,68,68,0.2)",
    color: "#f87171",
    border: "1px solid rgba(239,68,68,0.3)",
  },
  learning: {
    backgroundColor: "rgba(20,184,166,0.2)",
    color: "#2dd4bf",
    border: "1px solid rgba(20,184,166,0.3)",
  },
  score: {
    backgroundColor: "rgba(245,158,11,0.2)",
    color: "#fbbf24",
    border: "1px solid rgba(245,158,11,0.3)",
  },
};

const PRIORITY_CLASS: Record<string, string> = {
  p0: "cc-tag-p0",
  p1: "cc-tag-p1",
  p2: "cc-tag-p2",
  p3: "cc-tag-p3",
};

const FILTER_OPTIONS = [
  { value: "all", label: "All Types" },
  { value: "action", label: "Actions" },
  { value: "alert", label: "Alerts" },
  { value: "learning", label: "Learnings" },
  { value: "score", label: "Scores" },
];

export default function BeadsKanban({ beads, onBeadClick }: BeadsKanbanProps) {
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [hoveredCard, setHoveredCard] = useState<string | null>(null);
  const [hoveredCol, setHoveredCol] = useState<string | null>(null);

  const filtered =
    typeFilter === "all" ? beads : beads.filter((b) => b.type === typeFilter);

  const byCol: Record<string, Bead[]> = {};
  for (const c of COLS) byCol[c.id] = [];
  for (const b of filtered) {
    const colId = col(b);
    if (byCol[colId]) byCol[colId].push(b);
  }

  return (
    <div className="cc-panel" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <span
          className="cc-panel-title"
          style={{ fontFamily: "var(--font-heading)", letterSpacing: "0.08em" }}
        >
          BEADS QUEUE
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <select
            className="chromatic-input"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            style={{
              fontSize: 11,
              padding: "3px 8px",
              height: 28,
              borderRadius: 4,
              cursor: "pointer",
            }}
          >
            {FILTER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            className="chromatic-button chromatic-button-ghost"
            style={{ fontSize: 11, padding: "3px 10px", height: 28 }}
          >
            + NEW BEAD
          </button>
        </div>
      </div>

      {/* Columns row */}
      <div
        className="cc-scrollable"
        style={{
          display: "flex",
          gap: 10,
          overflowX: "auto",
          paddingBottom: 4,
        }}
      >
        {COLS.map((colDef) => {
          const cards = byCol[colDef.id] || [];
          const isHoveredCol = hoveredCol === colDef.id;

          return (
            <div
              key={colDef.id}
              style={{
                minWidth: 170,
                flexShrink: 0,
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              {/* Column header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.1em",
                    color: colDef.color,
                    fontFamily: "var(--font-heading)",
                  }}
                >
                  {colDef.label}
                </span>
                <span
                  style={{
                    fontSize: 8,
                    padding: "2px 6px",
                    borderRadius: 9999,
                    backgroundColor: colDef.color + "26",
                    color: colDef.countColor,
                    fontFamily: "var(--font-mono)",
                    fontWeight: 600,
                  }}
                >
                  {cards.length}
                </span>
              </div>

              {/* View Board link */}
              <div>
                <span
                  style={{
                    fontSize: 9,
                    color: "var(--cc-muted, var(--color-text-muted))",
                    cursor: "pointer",
                    textDecoration: "none",
                    transition: "color var(--duration-fast)",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLSpanElement).style.color =
                      colDef.color;
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLSpanElement).style.color =
                      "var(--cc-muted, var(--color-text-muted))";
                  }}
                >
                  View Board →
                </span>
              </div>

              {/* Cards area */}
              <div
                className="cc-scrollable"
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 5,
                  maxHeight: 280,
                  overflowY: "auto",
                }}
              >
                {cards.length === 0 ? (
                  <div
                    style={{
                      fontSize: 9,
                      color: "var(--cc-muted, var(--color-text-muted))",
                      fontStyle: "italic",
                      textAlign: "center",
                      padding: "16px 0",
                    }}
                  >
                    No items
                  </div>
                ) : (
                  cards.map((bead) => {
                    const isHovered = hoveredCard === bead.bead_id;
                    return (
                      <div
                        key={bead.bead_id}
                        onClick={() => onBeadClick?.(bead)}
                        onMouseEnter={() => setHoveredCard(bead.bead_id)}
                        onMouseLeave={() => setHoveredCard(null)}
                        style={{
                          padding: "8px 10px",
                          borderRadius: 6,
                          background: "rgba(0,0,0,0.3)",
                          border: `1px solid ${
                            isHovered
                              ? colDef.color + "66"
                              : "var(--color-border)"
                          }`,
                          cursor: "pointer",
                          transition:
                            "border-color var(--duration-fast, 150ms) var(--ease-out)",
                        }}
                      >
                        {/* Top row: priority + type */}
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                            flexWrap: "wrap",
                          }}
                        >
                          <span className={PRIORITY_CLASS[bead.priority]}>
                            {bead.priority.toUpperCase()}
                          </span>
                          <span
                            style={{
                              fontSize: 8,
                              padding: "1px 5px",
                              borderRadius: 3,
                              fontFamily: "var(--font-mono)",
                              fontWeight: 600,
                              letterSpacing: "0.05em",
                              textTransform: "uppercase",
                              ...TYPE_BADGE_STYLE[bead.type],
                            }}
                          >
                            {bead.type}
                          </span>
                        </div>

                        {/* Title */}
                        <div
                          style={{
                            fontSize: 11,
                            color: "var(--color-text-primary)",
                            margin: "4px 0",
                            lineHeight: 1.4,
                            maxHeight: "2.8em",
                            overflow: "hidden",
                            fontFamily: "var(--font-body)",
                          }}
                        >
                          {bead.title}
                        </div>

                        {/* Bottom row: source + bead_id */}
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: 4,
                          }}
                        >
                          <span
                            style={{
                              fontSize: 9,
                              color:
                                "var(--cc-muted, var(--color-text-muted))",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                              maxWidth: "60%",
                            }}
                          >
                            {bead.source}
                          </span>
                          <span
                            style={{
                              fontSize: 9,
                              color:
                                "var(--cc-muted, var(--color-text-muted))",
                              fontFamily: "var(--font-mono)",
                              opacity: 0.7,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {bead.bead_id.slice(0, 8)}
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
