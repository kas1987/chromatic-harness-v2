/**
 * nsfw-grade.ts
 *
 * POST /nsfw/grade                — trigger vision grading for a batch
 * GET  /nsfw/grade                — list all grade jobs this session
 * GET  /nsfw/grade/stream         — SSE subscription on nsfw-grades channel
 * GET  /nsfw/grade/:batch         — get status of a specific batch
 * GET  /nsfw/grade/:batch/results — full grades array from disk
 * GET  /nsfw/grade/:batch/summary — grade distribution summary
 */

import { Router, Request, Response } from "express";
import { randomUUID } from "crypto";
import type { ChannelBroadcaster } from "../channels/channel-broadcaster";
import {
  spawnGradeJob,
  getJob,
  listJobs,
  readGrades,
  computeGradeSummary,
  initializeNsfwGradeService,
} from "../services/nsfw-grade-service";

export const nsfwGradeRouter = Router();

let broadcaster: ChannelBroadcaster | null = null;

export function initializeNsfwGradeRouter(bc: ChannelBroadcaster): void {
  broadcaster = bc;
  initializeNsfwGradeService(bc);
}

// ── POST /nsfw/grade ───────────────────────────────────────────────────────────
// Body: { batch: "b72", model?: "ollama" }
nsfwGradeRouter.post("/", (req: Request, res: Response) => {
  const { batch, model } = req.body ?? {};

  if (!batch || typeof batch !== "string" || !/^b\d+$/.test(batch)) {
    return res.status(400).json({ error: "batch is required and must match /^b\\d+$/" });
  }

  try {
    const job = spawnGradeJob(batch, model ?? "ollama");
    return res.status(202).json({
      accepted: true,
      batch: job.batch,
      status: job.status,
      startedAt: job.startedAt,
      logPath: job.logPath,
      gradesPath: job.gradesPath,
      reportPath: job.reportPath,
    });
  } catch (err) {
    const msg = (err as Error).message;
    if (msg.includes("already running")) {
      return res.status(409).json({ error: msg, job: getJob(batch) });
    }
    console.error("[nsfw-grade] spawn error:", err);
    return res.status(500).json({ error: "Failed to spawn grader" });
  }
});

// ── GET /nsfw/grade ────────────────────────────────────────────────────────────
nsfwGradeRouter.get("/", (_req: Request, res: Response) => {
  return res.json(listJobs());
});

// ── GET /nsfw/grade/stream ─────────────────────────────────────────────────────
// SSE endpoint — must be registered BEFORE /:batch to avoid param collision
nsfwGradeRouter.get("/stream", (req: Request, res: Response) => {
  if (!broadcaster) {
    return res.status(503).json({ error: "Broadcaster not initialized" });
  }

  const sessionId = randomUUID();
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");
  res.flushHeaders();

  broadcaster.subscribe(sessionId, "nsfw-grades", [], res);

  // Heartbeat every 30s to keep connection alive
  const heartbeat = setInterval(() => {
    try {
      res.write(": heartbeat\n\n");
    } catch {
      clearInterval(heartbeat);
    }
  }, 30_000);

  req.on("close", () => {
    clearInterval(heartbeat);
    broadcaster?.unsubscribe(sessionId);
  });
});

// ── GET /nsfw/grade/:batch/results ─────────────────────────────────────────────
nsfwGradeRouter.get("/:batch/results", (req: Request, res: Response) => {
  try {
    const grades = readGrades(req.params.batch);
    return res.json({ batch: req.params.batch, grades });
  } catch {
    return res.status(404).json({
      error: `No grades found for batch '${req.params.batch}'. Run grader first.`,
    });
  }
});

// ── GET /nsfw/grade/:batch/summary ─────────────────────────────────────────────
nsfwGradeRouter.get("/:batch/summary", (req: Request, res: Response) => {
  try {
    const grades = readGrades(req.params.batch);
    const summary = computeGradeSummary(grades);
    return res.json({ batch: req.params.batch, ...summary });
  } catch {
    return res.status(404).json({
      error: `No grades found for batch '${req.params.batch}'. Run grader first.`,
    });
  }
});

// ── GET /nsfw/grade/:batch ─────────────────────────────────────────────────────
nsfwGradeRouter.get("/:batch", (req: Request, res: Response) => {
  const job = getJob(req.params.batch);
  if (!job) {
    return res.status(404).json({
      error: `No grade job found for batch '${req.params.batch}'`,
    });
  }
  return res.json(job);
});
