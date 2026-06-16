"use client";

/**
 * Console mode runtime.
 *
 * Holds the active console mode (Operator / Auditor / Designer) and persists the
 * choice to localStorage. Modes are advisory/UI-only — see lib/modes.ts. This
 * mirrors the theme runtime (lib/theme.tsx) intentionally.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  MODES,
  DEFAULT_MODE_ID,
  getMode,
  type ConsoleMode,
} from "./modes";

// Re-export the mode type so consumers import everything mode-related from "@/lib/mode".
export type { ConsoleMode } from "./modes";

const STORAGE_KEY = "cc.modeId";

interface ModeContextValue {
  mode: ConsoleMode;
  modeId: string;
  setModeId: (id: string) => void;
  modes: ConsoleMode[];
}

const ModeContext = createContext<ModeContextValue | null>(null);

export function ModeProvider({ children }: { children: React.ReactNode }) {
  const [modeId, setModeIdState] = useState<string>(DEFAULT_MODE_ID);

  // Load the persisted choice only after mount to avoid SSR/hydration mismatch.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved && MODES.some((m) => m.id === saved)) {
        setModeIdState(saved);
      }
    } catch {
      /* localStorage unavailable — keep default */
    }
  }, []);

  const mode = getMode(modeId);

  const setModeId = useCallback((id: string) => {
    setModeIdState(id);
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* ignore persistence failure */
    }
  }, []);

  return (
    <ModeContext.Provider value={{ mode, modeId, setModeId, modes: MODES }}>
      {children}
    </ModeContext.Provider>
  );
}

export function useMode(): ModeContextValue {
  const ctx = useContext(ModeContext);
  if (!ctx) {
    throw new Error("useMode must be used within a ModeProvider");
  }
  return ctx;
}
