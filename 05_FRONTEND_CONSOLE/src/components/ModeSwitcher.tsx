"use client";

/**
 * Console mode selector for the Command Center header.
 *
 * Mirrors ThemeSwitcher. Modes are advisory/UI-only (see lib/modes.ts) — selecting
 * a mode changes labels, hints, and panel emphasis but never overrides CMP or gates.
 */

import { useMode } from "@/lib/mode";

export default function ModeSwitcher() {
  const { modeId, setModeId, modes } = useMode();

  return (
    <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
      <span
        style={{
          fontSize: 10,
          color: "var(--cc-muted)",
          textTransform: "uppercase",
          letterSpacing: 1,
        }}
      >
        Mode
      </span>
      <select
        aria-label="Mode"
        value={modeId}
        onChange={(e) => setModeId(e.target.value)}
        style={{
          background: "var(--cc-panel-bg)",
          color: "var(--cc-text)",
          border: "1px solid var(--cc-panel-border)",
          borderRadius: 3,
          fontSize: 11,
          fontFamily: "monospace",
          padding: "2px 6px",
          cursor: "pointer",
        }}
      >
        {modes.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name}
          </option>
        ))}
      </select>
    </label>
  );
}
