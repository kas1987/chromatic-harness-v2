/**
 * Console mode definitions.
 *
 * Modes are ADVISORY / UI-ONLY: they change labels, hints, and panel emphasis in
 * the Command Center. They do NOT override CMP, gates, or autonomy enforcement —
 * the runtime remains the sole authority on what may execute.
 *
 * This module is typed in source (no YAML parsing), mirroring how the theme layer
 * consumes a generated, statically-typed list.
 */

export interface ConsoleMode {
  id: "operator" | "auditor" | "designer";
  name: string;
  primaryAction: string;
  autonomyBand: string;
  hint: string;
  mutating: boolean;
}

export const MODES: ConsoleMode[] = [
  {
    id: "operator",
    name: "Operator",
    primaryAction: "GO",
    autonomyBand: "L3-L4",
    hint: "Execution & dispatch. Confidence-gated.",
    mutating: true,
  },
  {
    id: "auditor",
    name: "Auditor",
    primaryAction: "RUN AUDIT",
    autonomyBand: "L0-L2",
    hint: "Read-only inspection & evidence. Non-mutating unless CMP-promoted.",
    mutating: false,
  },
  {
    id: "designer",
    name: "Designer",
    primaryAction: "GENERATE MOCKUP",
    autonomyBand: "L1-L3",
    hint: "Visual/theme composition. Cannot touch runtime.",
    mutating: true,
  },
];

export const DEFAULT_MODE_ID: ConsoleMode["id"] = "operator";

export function getMode(id: string | null | undefined): ConsoleMode {
  return MODES.find((m) => m.id === id) ?? getDefaultMode();
}

function getDefaultMode(): ConsoleMode {
  // MODES always contains DEFAULT_MODE_ID, so this never falls through.
  return MODES.find((m) => m.id === DEFAULT_MODE_ID) ?? MODES[0];
}
