/**
 * nsfw-grade-service.ts
 *
 * Spawns nsfw_vision_grader.py as a background subprocess after ComfyUI batch
 * completion. Tracks running/completed grade jobs in memory (per-session).
 * Grade artifacts are written to disk by the grader itself.
 * Broadcasts completion events via ChannelBroadcaster on the "nsfw-grades" channel.
 */

import { spawn } from "child_process";
import path from "path";
import fs from "fs";
import type { ChannelBroadcaster } from "../channels/channel-broadcaster";

// ── Broadcaster injection ──────────────────────────────────────────────────────
let broadcaster: ChannelBroadcaster | null = null;

export function initializeNsfwGradeService(bc: ChannelBroadcaster): void {
  broadcaster = bc;
}

// ── Types ──────────────────────────────────────────────────────────────────────
export type GradeJobStatus = "running" | "completed" | "failed";

export type GradeTier = "S+" | "S" | "A+" | "A" | "B+" | "B" | "C" | "F";

export interface GradeEntry {
  archetype: string;
  batch: string;
  ethnicity_fidelity: number;
  skin_tone_accuracy: number;
  bust_size: "too_small" | "correct" | "too_big";
  bust_shape: "natural_sag" | "perky" | "pendulous" | "correct";
  act_success: number;
  overall_quality: number;
  grade: GradeTier;
  notes: string;
  recommended_adjustments: string[];
  lock_seed: boolean;
}

export interface GradeJob {
  batch: string;
  status: GradeJobStatus;
  startedAt: string;
  completedAt?: string;
  exitCode?: number;
  logPath: string;
  gradesPath: string;
  reportPath: string;
}

export interface GradeSummary {
  total: number;
  distribution: Partial<Record<GradeTier, string[]>>;
  lockSeeds: string[];
  needsWork: string[];
}

// ── Constants ──────────────────────────────────────────────────────────────────
const GRADE_TIERS: GradeTier[] = ["S+", "S", "A+", "A", "B+", "B", "C", "F"];
const NEEDS_WORK_TIERS: GradeTier[] = ["C", "F", "B", "B+"];

// ── In-memory job registry ─────────────────────────────────────────────────────
const jobs = new Map<string, GradeJob>();

// ── Path helpers ───────────────────────────────────────────────────────────────
function repoRoot(): string {
  // gen/dist/services → gen/dist → gen → repo root
  return path.resolve(__dirname, "..", "..", "..");
}

function graderScript(): string {
  return path.join(repoRoot(), "scripts", "generation", "nsfw_vision_grader.py");
}

function gradesDir(): string {
  return path.join(repoRoot(), ".agents", "nsfw", "grades");
}

// ── Public accessors ───────────────────────────────────────────────────────────
export function getJob(batch: string): GradeJob | null {
  return jobs.get(batch) ?? null;
}

export function listJobs(): GradeJob[] {
  return [...jobs.values()].sort((a, b) => b.startedAt.localeCompare(a.startedAt));
}

export function readGrades(batch: string): GradeEntry[] {
  const p = path.join(gradesDir(), `${batch}_grades.json`);
  const raw = fs.readFileSync(p, "utf-8");
  return JSON.parse(raw) as GradeEntry[];
}

export function computeGradeSummary(grades: GradeEntry[]): GradeSummary {
  const distribution: Partial<Record<GradeTier, string[]>> = {};
  for (const t of GRADE_TIERS) distribution[t] = [];
  for (const g of grades) {
    distribution[g.grade]?.push(g.archetype);
  }
  // Drop empty tiers
  for (const t of GRADE_TIERS) {
    if (distribution[t]?.length === 0) delete distribution[t];
  }
  return {
    total: grades.length,
    distribution,
    lockSeeds: grades.filter((g) => g.lock_seed).map((g) => g.archetype),
    needsWork: grades
      .filter((g) => (NEEDS_WORK_TIERS as string[]).includes(g.grade))
      .map((g) => g.archetype),
  };
}

// ── Broadcast helpers ──────────────────────────────────────────────────────────
function broadcastComplete(batch: string, grades: GradeEntry[]): void {
  if (!broadcaster) {
    console.warn(`[nsfw-grade] Broadcaster not initialized — skipping completion broadcast for ${batch}`);
    return;
  }
  const summary = computeGradeSummary(grades);
  const event = broadcaster.makeChannelEvent(
    "nsfw-grades",
    "nsfw.grade.complete",
    {
      batch,
      totalGraded: summary.total,
      gradeDistribution: summary.distribution as Record<string, unknown>,
      lockSeeds: summary.lockSeeds,
      needsWork: summary.needsWork,
    },
    "internal"
  );
  broadcaster.broadcast("nsfw-grades", event);
}

function broadcastFailed(batch: string, exitCode: number): void {
  if (!broadcaster) return;
  const event = broadcaster.makeChannelEvent(
    "nsfw-grades",
    "nsfw.grade.failed",
    { batch, exitCode },
    "internal"
  );
  broadcaster.broadcast("nsfw-grades", event);
}

// ── Core spawn ─────────────────────────────────────────────────────────────────
/**
 * Spawn nsfw_vision_grader.py for the given batch prefix.
 * Returns immediately — grading runs in the background.
 * Throws if a grade job for this batch is already running.
 */
export function spawnGradeJob(batch: string, model = "ollama"): GradeJob {
  const existing = jobs.get(batch);
  if (existing && existing.status === "running") {
    throw new Error(`Grade job for batch '${batch}' is already running`);
  }

  const gDir = gradesDir();
  fs.mkdirSync(gDir, { recursive: true });

  const logPath    = path.join(gDir, `${batch}_grader.log`);
  const gradesPath = path.join(gDir, `${batch}_grades.json`);
  const reportPath = path.join(gDir, `${batch}_report.md`);

  const job: GradeJob = {
    batch,
    status: "running",
    startedAt: new Date().toISOString(),
    logPath,
    gradesPath,
    reportPath,
  };
  jobs.set(batch, job);

  const script    = graderScript();
  const logStream = fs.createWriteStream(logPath, { flags: "w" });

  const child = spawn("python", [script, "--batch", batch, "--model", model], {
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });

  child.stdout?.pipe(logStream);
  child.stderr?.pipe(logStream);

  child.on("close", (code) => {
    const j = jobs.get(batch)!;
    j.completedAt = new Date().toISOString();
    j.exitCode = code ?? -1;
    j.status = code === 0 ? "completed" : "failed";
    logStream.end();

    console.log(
      `[nsfw-grade] Batch ${batch} grading ${j.status} (exit=${code}) → ${reportPath}`
    );

    if (code === 0) {
      try {
        const grades = readGrades(batch);
        broadcastComplete(batch, grades);
      } catch (err) {
        console.error(`[nsfw-grade] Failed to read grades for broadcast (batch=${batch}):`, (err as Error).message);
      }
    } else {
      broadcastFailed(batch, code ?? -1);
    }
  });

  child.on("error", (err) => {
    const j = jobs.get(batch)!;
    j.status = "failed";
    j.completedAt = new Date().toISOString();
    logStream.end(`\n[spawn error] ${err.message}\n`);
    console.error(`[nsfw-grade] Spawn error for batch ${batch}:`, err.message);
    broadcastFailed(batch, -1);
  });

  console.log(`[nsfw-grade] Started grader for batch ${batch} (pid=${child.pid})`);
  return job;
}
