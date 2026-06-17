"use client";

/**
 * Asset-pack (theme) selector for the Command Center header.
 *
 * Options are data-driven from the generated THEMES list, so a theme only appears
 * once its asset pack actually ships (e.g. the unshipped "Storm Console" pack does
 * not render a broken option).
 */

import { useTheme } from "@/lib/theme";

export default function ThemeSwitcher() {
  const { themeId, setThemeId, themes } = useTheme();

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
        Asset Pack
      </span>
      <select
        aria-label="Asset pack"
        value={themeId}
        onChange={(e) => setThemeId(e.target.value)}
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
        {themes.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </select>
    </label>
  );
}
