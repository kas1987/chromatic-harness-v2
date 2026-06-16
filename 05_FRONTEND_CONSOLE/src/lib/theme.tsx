"use client";

/**
 * Console theme runtime.
 *
 * Holds the active asset pack (theme), persists the choice to localStorage, and
 * mirrors the active theme onto CSS custom properties (`--cc-*`) so server-rendered
 * chrome (layout body) can react without prop drilling. Themes themselves are
 * generated from assets/prompt_variants/*.asset_pack.yaml by
 * scripts/generate_console_themes.py — this module never parses YAML.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  THEMES,
  DEFAULT_THEME_ID,
  getTheme,
  type ConsoleTheme,
} from "./themes.generated";

// Re-export the theme type so consumers import everything theme-related from "@/lib/theme".
export type { ConsoleTheme } from "./themes.generated";

const STORAGE_KEY = "cc.themeId";

interface ThemeContextValue {
  theme: ConsoleTheme;
  themeId: string;
  setThemeId: (id: string) => void;
  themes: ConsoleTheme[];
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const CSS_VARS: Array<[string, keyof ConsoleTheme]> = [
  ["--cc-bg", "bg"],
  ["--cc-panel-bg", "panelBg"],
  ["--cc-panel-border", "panelBorder"],
  ["--cc-heading", "heading"],
  ["--cc-text", "text"],
  ["--cc-muted", "muted"],
  ["--cc-accent", "accent"],
  ["--cc-brand", "brand"],
  ["--cc-success", "success"],
  ["--cc-warning", "warning"],
  ["--cc-danger", "danger"],
  ["--cc-info", "info"],
];

function applyCssVars(theme: ConsoleTheme) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  for (const [varName, key] of CSS_VARS) {
    root.style.setProperty(varName, String(theme[key]));
  }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [themeId, setThemeIdState] = useState<string>(DEFAULT_THEME_ID);

  // Load the persisted choice only after mount to avoid SSR/hydration mismatch.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved && THEMES.some((t) => t.id === saved)) {
        setThemeIdState(saved);
      }
    } catch {
      /* localStorage unavailable — keep default */
    }
  }, []);

  const theme = getTheme(themeId);

  useEffect(() => {
    applyCssVars(theme);
  }, [theme]);

  const setThemeId = useCallback((id: string) => {
    setThemeIdState(id);
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* ignore persistence failure */
    }
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, themeId, setThemeId, themes: THEMES }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
