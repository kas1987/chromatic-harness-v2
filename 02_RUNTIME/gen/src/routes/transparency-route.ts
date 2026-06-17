import { Router, Request, Response } from "express";
import fs from "fs/promises";
import { agentTransparencyService } from "../transparency/agent-transparency.js";

/**
 * Transparency route — exposes the cross-agent operational snapshot.
 *
 * GET /transparency/status
 *   Returns a TransparencySnapshot with: activeLlm, routingConfidence,
 *   activeTasks, upcomingWork (from .agents/rpi/next-work.jsonl), driftAlerts.
 *
 * Use this endpoint to:
 *   - Check what LLM is currently active and how confident the routing was
 *   - See what work is coming up before starting a silo operation
 *   - Detect drift (suggested != actual LLM) that may indicate misconfiguration
 */
export const transparencyRouter = Router();

/**
 * Parse .agents/rpi/next-work.jsonl for unconsumed upcoming work items.
 * Each line is a JSON object: { consumed?: boolean, items?: [{title, severity}] }
 * Mixed formats in the file are handled with fail-open line-by-line parsing.
 */
async function readUpcomingWork(): Promise<Array<{ title: string; severity: string }>> {
  const NEXT_WORK_PATH = ".agents/rpi/next-work.jsonl";
  try {
    const text = await fs.readFile(NEXT_WORK_PATH, "utf-8");
    const results: Array<{ title: string; severity: string }> = [];

    for (const line of text.split("\n").filter(Boolean)) {
      try {
        const obj = JSON.parse(line) as {
          consumed?: boolean;
          items?: Array<{ title?: string; severity?: string }>;
        };
        if (obj.consumed === true) continue; // skip already-consumed entries
        for (const item of obj.items ?? []) {
          if (item.title) {
            results.push({ title: item.title, severity: item.severity ?? "low" });
          }
        }
      } catch {
        // Skip malformed lines — fail open, don't crash the route
      }
    }

    return results.slice(0, 10); // cap at 10 for hook injection payload size
  } catch {
    return []; // file missing or unreadable → empty list, not an error
  }
}

transparencyRouter.get("/status", async (_req: Request, res: Response) => {
  try {
    // Build a snapshot with current state
    // activeLlm and routingConfidence are best-effort from the singleton service;
    // in a full implementation these would be populated from the session routing store.
    const snapshot = agentTransparencyService.buildSnapshot(
      "claude", // default: claude is always available
      1.0,
      [],
    );

    // Populate upcomingWork from next-work.jsonl (outside the snapshot builder to avoid fs coupling)
    snapshot.upcomingWork = await readUpcomingWork();

    res.json({
      ok: true,
      snapshot,
      driftRate: agentTransparencyService.getDriftRate(),
    });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
});

transparencyRouter.get("/drift", (_req: Request, res: Response) => {
  res.json({
    ok: true,
    alerts: agentTransparencyService.getRecentDrift(),
    driftRate: agentTransparencyService.getDriftRate(),
  });
});
