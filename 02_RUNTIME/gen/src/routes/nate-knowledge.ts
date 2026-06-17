/**
 * POST /nate/query — query Nate's newsletter knowledge base.
 *
 * Request body: { query: string, limit?: number, source?: "post"|"kit"|"guide" }
 * Response:     KnowledgeResult[]  (empty array if Nate unavailable — fail-open)
 */

import { Router, Request, Response } from "express";
import { getNateClient, type KnowledgeResult } from "../services/nate-client";

export const nateKnowledgeRouter = Router();

interface QueryBody {
  query?: unknown;
  limit?: unknown;
  source?: unknown;
}

// POST /nate/query
nateKnowledgeRouter.post("/query", async (req: Request, res: Response) => {
  const body = (req.body ?? {}) as QueryBody;

  if (!body.query || typeof body.query !== "string" || !body.query.trim()) {
    return res.status(400).json({ error: "query is required and must be a non-empty string" });
  }

  const query = body.query.trim();
  const limit = typeof body.limit === "number" && body.limit > 0
    ? Math.min(body.limit, 50)
    : 8;
  const source = ["post", "kit", "guide"].includes(body.source as string)
    ? (body.source as "post" | "kit" | "guide")
    : ("" as const);

  try {
    const nateClient = getNateClient();
    const results: KnowledgeResult[] = await nateClient.query(query, limit, source);
    return res.json(results);
  } catch (err) {
    // Fail-open: return empty array rather than 500
    console.warn("[nate/query] Unexpected error (fail-open):", (err as Error).message);
    return res.json([] as KnowledgeResult[]);
  }
});

// GET /nate/status — health check
nateKnowledgeRouter.get("/status", async (_req: Request, res: Response) => {
  try {
    const nateClient = getNateClient();
    const stats = await nateClient.ping();
    if (stats === null) {
      return res.json({ available: false });
    }
    return res.json({ available: true, ...stats });
  } catch {
    return res.json({ available: false });
  }
});
