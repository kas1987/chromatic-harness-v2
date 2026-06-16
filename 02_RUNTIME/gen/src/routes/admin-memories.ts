import { Router, Request, Response } from "express";
import { AdminMemoryService, ListMemoriesFilters, UpdateMemoryPatch } from "../services/admin-memory-service";
import { MemoryScope, MemoryKind, SensitivityLevel } from "../memory/ids";

let adminMemoryService: AdminMemoryService | null = null;

export function initializeAdminMemoriesRouter(service: AdminMemoryService): void {
  adminMemoryService = service;
}

function getService(): AdminMemoryService {
  if (!adminMemoryService) {
    throw new Error("AdminMemoryService not initialized");
  }
  return adminMemoryService;
}

export const adminMemoriesRouter = Router();

// GET /admin/memories
adminMemoriesRouter.get("/", (req: Request, res: Response): void => {
  try {
    const filters: ListMemoriesFilters = {
      limit: req.query.limit ? parseInt(req.query.limit as string, 10) : 50,
      offset: req.query.offset ? parseInt(req.query.offset as string, 10) : 0,
    };

    if (req.query.projectId) filters.projectId = req.query.projectId as string;
    if (req.query.scope) filters.scope = req.query.scope as MemoryScope;
    if (req.query.sensitivity) filters.sensitivity = req.query.sensitivity as SensitivityLevel;
    if (req.query.kind) filters.kind = req.query.kind as MemoryKind;

    const result = getService().listMemories(filters);
    res.json({ items: result.items, total: result.total, limit: filters.limit, offset: filters.offset });
  } catch (err) {
    console.error("GET /admin/memories error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// GET /admin/memories/:id
adminMemoriesRouter.get("/:id", (req: Request, res: Response): void => {
  try {
    const memory = getService().getMemory(req.params.id);
    if (!memory) {
      res.status(404).json({ error: "Memory not found" });
      return;
    }
    res.json(memory);
  } catch (err) {
    console.error("GET /admin/memories/:id error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// PATCH /admin/memories/:id
adminMemoriesRouter.patch("/:id", (req: Request, res: Response): void => {
  try {
    const patch: UpdateMemoryPatch = {};
    if (req.body.text !== undefined) patch.text = req.body.text;
    if (req.body.sensitivity !== undefined) patch.sensitivity = req.body.sensitivity;
    if ("expiresAt" in req.body) patch.expiresAt = req.body.expiresAt;

    const updated = getService().updateMemory(req.params.id, patch);
    res.json(updated);
  } catch (err: any) {
    if (err?.message?.includes("not found")) {
      res.status(404).json({ error: "Memory not found" });
      return;
    }
    console.error("PATCH /admin/memories/:id error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// DELETE /admin/memories/:id
adminMemoriesRouter.delete("/:id", (req: Request, res: Response): void => {
  try {
    const { reason } = req.body;
    if (!reason || typeof reason !== "string" || reason.trim() === "") {
      res.status(400).json({ error: "reason is required" });
      return;
    }

    getService().deleteMemory(req.params.id, reason.trim());
    res.status(204).send();
  } catch (err: any) {
    if (err?.message?.includes("not found")) {
      res.status(404).json({ error: "Memory not found" });
      return;
    }
    console.error("DELETE /admin/memories/:id error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// POST /admin/memories/scan-confidential
adminMemoriesRouter.post("/scan-confidential", (req: Request, res: Response): void => {
  try {
    const { projectId } = req.body;
    const items = getService().scanConfidential(projectId);
    res.json({ items, count: items.length });
  } catch (err) {
    console.error("POST /admin/memories/scan-confidential error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// POST /admin/memories/find-stale
adminMemoriesRouter.post("/find-stale", (req: Request, res: Response): void => {
  try {
    const { olderThanDays } = req.body;
    if (typeof olderThanDays !== "number" || olderThanDays <= 0) {
      res.status(400).json({ error: "olderThanDays must be a positive number" });
      return;
    }

    const items = getService().findStale(olderThanDays);
    res.json({ items, count: items.length });
  } catch (err) {
    console.error("POST /admin/memories/find-stale error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
