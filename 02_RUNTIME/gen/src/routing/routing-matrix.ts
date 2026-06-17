import fs from "fs";
import path from "path";
import type { LlmProvider } from "../llm/llm-types.js";

const VALID_PROVIDERS = new Set<string>([
  "claude",
  "gpt",
  "gemini",
  "ollama",
  "lm-studio",
  "minimax",
  "gemma",
]);

export interface RoutingStep {
  provider: LlmProvider;
  /** Ollama model tag for `ollama` / `gemma` steps; omitted uses Gen env defaults. */
  localModelTag?: string;
}

interface MatrixEntry {
  steps: Array<{ provider: string; localModelTag?: string }>;
}

type MatrixFile = Record<string, MatrixEntry>;

function resolveRoutingMatrixPath(): string | null {
  const candidates = [
    path.join(__dirname, "../routes/routing-matrix.json"),
    path.resolve(process.cwd(), "src/routes/routing-matrix.json"),
    path.resolve(process.cwd(), "dist/routes/routing-matrix.json"),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

function parseMatrix(raw: MatrixFile): Record<string, RoutingStep[]> {
  const out: Record<string, RoutingStep[]> = {};
  for (const [intent, entry] of Object.entries(raw)) {
    if (!entry?.steps || !Array.isArray(entry.steps)) continue;
    const steps: RoutingStep[] = [];
    for (const row of entry.steps) {
      if (!row?.provider || typeof row.provider !== "string") continue;
      if (!VALID_PROVIDERS.has(row.provider)) continue;
      const provider = row.provider as LlmProvider;
      const tag =
        typeof row.localModelTag === "string" && row.localModelTag.trim()
          ? row.localModelTag.trim()
          : undefined;
      if (tag && provider !== "ollama" && provider !== "gemma") {
        steps.push({ provider });
      } else {
        steps.push(tag ? { provider, localModelTag: tag } : { provider });
      }
    }
    if (steps.length > 0) out[intent] = steps;
  }
  return out;
}

let _cached: Record<string, RoutingStep[]> | null = null;
let _warnedMissing = false;

function loadMatrix(): Record<string, RoutingStep[]> {
  if (_cached) return _cached;
  const p = resolveRoutingMatrixPath();
  if (!p) {
    if (!_warnedMissing) {
      console.warn("[routing-matrix] routing-matrix.json not found — taskIntent matrix routing disabled");
      _warnedMissing = true;
    }
    _cached = {};
    return _cached;
  }
  try {
    const text = fs.readFileSync(p, "utf-8");
    const raw = JSON.parse(text) as MatrixFile;
    _cached = parseMatrix(raw);
    return _cached;
  } catch (e) {
    console.warn("[routing-matrix] failed to load routing-matrix.json:", (e as Error).message);
    _cached = {};
    return _cached;
  }
}

/**
 * Returns ordered routing steps for a delegate `taskIntent`, or null if unknown / empty.
 * Keys match `routing-matrix.json` (e.g. classify-route, vision-triage).
 */
export function getRoutingSteps(taskIntent: string | undefined): RoutingStep[] | null {
  const key = taskIntent?.trim();
  if (!key) return null;
  const matrix = loadMatrix();
  const steps = matrix[key];
  if (!steps?.length) return null;
  return dedupeAdjacentSteps(steps);
}

/** Collapse consecutive identical provider+tag pairs (e.g. duplicate matrix rows). */
export function dedupeAdjacentSteps(steps: RoutingStep[]): RoutingStep[] {
  if (steps.length <= 1) return steps;
  const out: RoutingStep[] = [];
  for (const s of steps) {
    const prev = out[out.length - 1];
    if (
      prev &&
      prev.provider === s.provider &&
      (prev.localModelTag ?? "") === (s.localModelTag ?? "")
    ) {
      continue;
    }
    out.push(s);
  }
  return out;
}

/** Drop Ollama-backed steps when VRAM guard says light local models are unsafe. */
export function filterRoutingStepsForVram(
  steps: RoutingStep[],
  ollamaLightSafe: boolean,
): RoutingStep[] {
  if (ollamaLightSafe) return steps;
  return steps.filter((s) => s.provider !== "ollama" && s.provider !== "gemma");
}
