import { Router, Request, Response } from "express";
import { OllamaClient } from "../ollama/ollama-client";
import { OllamaTriage } from "../ollama/ollama-triage";

export const ollamaRouter = Router();

let ollamaClient: OllamaClient | null = null;
let ollamaTriage: OllamaTriage | null = null;

export function initializeOllamaRouter(
  client: OllamaClient,
  triage: OllamaTriage,
): void {
  ollamaClient = client;
  ollamaTriage = triage;
}

// GET /ollama/status — health + available models
ollamaRouter.get("/status", async (_req: Request, res: Response) => {
  if (!ollamaClient) {
    return res.json({ available: false, models: [], reason: "not_initialized" });
  }
  const available = await ollamaClient.isAvailable();
  const models = available ? await ollamaClient.listModels() : [];
  return res.json({ available, models });
});

// POST /ollama/triage — explore-intent triage gate
ollamaRouter.post("/triage", async (req: Request, res: Response) => {
  const { query } = req.body as { query?: string };
  if (!query || typeof query !== "string") {
    return res.status(400).json({ error: "query is required" });
  }
  if (!ollamaTriage) {
    return res.status(503).json({ error: "Ollama triage not initialized" });
  }
  try {
    const result = await ollamaTriage.triageExploreTask(query);
    return res.json(result);
  } catch (err) {
    console.error("Ollama triage error:", err);
    return res.status(500).json({ error: "Triage failed", canHandle: false });
  }
});
