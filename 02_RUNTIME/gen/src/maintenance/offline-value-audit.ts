import fs from "fs";
import path from "path";
import { OllamaClient } from "../ollama/ollama-client";
import { config } from "../config";

export interface OfflineAuditSample {
  filePath: string;
  extension: string;
  confidence: number;
  risk: "low" | "medium" | "high";
  latencyMs: number;
  ok: boolean;
  error?: string;
}

export interface OfflineValueAuditReport {
  generatedAt: string;
  model: string;
  rootsScanned: number;
  sampleCount: number;
  successCount: number;
  failureCount: number;
  avgConfidence: number;
  lowConfidenceCount: number;
  samples: OfflineAuditSample[];
}

const CANDIDATE_EXTENSIONS = new Set([".ts", ".tsx", ".js", ".jsx", ".py", ".md", ".json", ".yaml", ".yml"]);
const IGNORE_DIR_NAMES = new Set([
  ".git",
  ".next",
  "node_modules",
  "dist",
  "build",
  "coverage",
  "outputs",
  ".venv",
  "venv",
  "__pycache__",
]);

function repoRoot(): string {
  return path.resolve(__dirname, "../..");
}

function auditRootDir(): string {
  return path.join(repoRoot(), ".agents", "director-reviews", "architecture", "offline-audit");
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

function parseConfidence(value: unknown): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

function toRisk(value: unknown): "low" | "medium" | "high" {
  if (value === "low" || value === "medium" || value === "high") return value;
  return "medium";
}

function resolveWorkspaceRoots(): string[] {
  const iniPath = "C:\\AI-DJ\\workspace-map.ini";
  const fallback = [repoRoot()];
  if (!fs.existsSync(iniPath)) return fallback;

  const lines = fs.readFileSync(iniPath, "utf-8").split(/\r?\n/);
  const roots: string[] = [];
  let inWorkspaces = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
      inWorkspaces = trimmed.toLowerCase() === "[workspaces]";
      continue;
    }
    if (!inWorkspaces || trimmed.length === 0 || trimmed.startsWith(";")) continue;
    const eq = trimmed.indexOf("=");
    if (eq <= 0) continue;
    const value = trimmed.slice(eq + 1).trim();
    if (value.length > 0) roots.push(value);
  }

  return roots.length > 0 ? roots : fallback;
}

function selectSampleFiles(roots: string[], sampleCount: number, maxFileBytes: number): string[] {
  const selected: string[] = [];

  for (const root of roots) {
    if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) continue;
    const stack = [root];

    while (stack.length > 0 && selected.length < sampleCount) {
      const current = stack.pop() as string;
      let entries: fs.Dirent[] = [];
      try {
        entries = fs.readdirSync(current, { withFileTypes: true });
      } catch {
        continue;
      }

      entries.sort((a, b) => a.name.localeCompare(b.name));
      for (const entry of entries) {
        const abs = path.join(current, entry.name);
        if (entry.isDirectory()) {
          if (!IGNORE_DIR_NAMES.has(entry.name.toLowerCase())) {
            stack.push(abs);
          }
          continue;
        }

        if (!entry.isFile() || selected.length >= sampleCount) continue;
        const ext = path.extname(entry.name).toLowerCase();
        if (!CANDIDATE_EXTENSIONS.has(ext)) continue;
        const size = fs.statSync(abs).size;
        if (size <= 0 || size > maxFileBytes) continue;
        selected.push(abs);
      }
    }

    if (selected.length >= sampleCount) break;
  }

  return selected;
}

function buildAuditPrompt(filePath: string, content: string): string {
  return [
    "You are auditing offline model value for engineering repo analysis.",
    `File: ${filePath}`,
    "Task: infer the file's purpose and expected maintenance risk from this snippet.",
    "Return ONLY valid JSON with exactly this shape:",
    '{"confidence":0.0,"risk":"low|medium|high","notes":"one sentence"}',
    "Confidence must be from 0.0 to 1.0.",
    "Snippet:",
    "---",
    content,
    "---",
  ].join("\n");
}

export async function runOfflineValueAudit(options?: {
  sampleCount?: number;
  maxFileBytes?: number;
  model?: string;
}): Promise<OfflineValueAuditReport> {
  const sampleCount = Math.max(1, Math.min(options?.sampleCount ?? 6, 20));
  const maxFileBytes = Math.max(512, options?.maxFileBytes ?? 16_000);
  const model = options?.model?.trim() || config.ollamaModel;

  const roots = resolveWorkspaceRoots();
  const files = selectSampleFiles(roots, sampleCount, maxFileBytes);
  const client = new OllamaClient(config.ollamaUrl, 20_000);

  const samples: OfflineAuditSample[] = [];
  for (const filePath of files) {
    const ext = path.extname(filePath).toLowerCase() || "(none)";
    let content = "";
    try {
      content = fs.readFileSync(filePath, "utf-8").slice(0, maxFileBytes);
    } catch (err) {
      samples.push({
        filePath,
        extension: ext,
        confidence: 0,
        risk: "high",
        latencyMs: 0,
        ok: false,
        error: (err as Error).message,
      });
      continue;
    }

    const t0 = Date.now();
    try {
      const result = await client.generateJSON<{ confidence?: number; risk?: string }>(
        model,
        buildAuditPrompt(filePath, content),
        { temperature: 0.1, num_predict: 128 },
      );

      const latencyMs = Date.now() - t0;
      if (!result) {
        samples.push({
          filePath,
          extension: ext,
          confidence: 0,
          risk: "high",
          latencyMs,
          ok: false,
          error: "No JSON response",
        });
        continue;
      }

      samples.push({
        filePath,
        extension: ext,
        confidence: parseConfidence(result.confidence),
        risk: toRisk(result.risk),
        latencyMs,
        ok: true,
      });
    } catch (err) {
      samples.push({
        filePath,
        extension: ext,
        confidence: 0,
        risk: "high",
        latencyMs: Date.now() - t0,
        ok: false,
        error: (err as Error).message,
      });
    }
  }

  const success = samples.filter((s) => s.ok);
  const avgConfidence =
    success.length > 0
      ? round2(success.reduce((acc, item) => acc + item.confidence, 0) / success.length)
      : 0;
  const lowConfidenceCount = success.filter((s) => s.confidence < 0.6).length;
  const failureCount = samples.length - success.length;

  const report: OfflineValueAuditReport = {
    generatedAt: new Date().toISOString(),
    model,
    rootsScanned: roots.length,
    sampleCount: samples.length,
    successCount: success.length,
    failureCount,
    avgConfidence,
    lowConfidenceCount,
    samples,
  };

  const root = auditRootDir();
  fs.mkdirSync(root, { recursive: true });
  const stamp = report.generatedAt.replace(/[:.]/g, "-");
  const datedPath = path.join(root, `${stamp}.json`);
  const latestPath = path.join(root, "latest.json");
  const raw = JSON.stringify(report, null, 2);
  fs.writeFileSync(datedPath, raw, "utf-8");
  fs.writeFileSync(latestPath, raw, "utf-8");

  return report;
}

export function readLatestOfflineValueAudit(): OfflineValueAuditReport | null {
  const latestPath = path.join(auditRootDir(), "latest.json");
  if (!fs.existsSync(latestPath)) return null;
  try {
    const parsed = JSON.parse(fs.readFileSync(latestPath, "utf-8")) as OfflineValueAuditReport;
    if (!parsed || typeof parsed.generatedAt !== "string") return null;
    return parsed;
  } catch {
    return null;
  }
}
