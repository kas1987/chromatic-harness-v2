import { Router, Request, Response } from "express";
import {
  MaintenanceStore,
  type CreateMaintenanceRecordInput,
  type MaintenanceConfidence,
  type MaintenancePriority,
  type MaintenanceSeverity,
  type MaintenanceStatus,
} from "../maintenance/maintenance-store";
import { readLatestOfflineValueAudit, runOfflineValueAudit } from "../maintenance/offline-value-audit";
import { isOfflineAuditEnabled } from "./admin-modes";

export const adminMaintenanceRouter = Router();

let maintenanceStore: MaintenanceStore | null = null;

export function initializeAdminMaintenanceRouter(store: MaintenanceStore): void {
  maintenanceStore = store;
}

function getStore(): MaintenanceStore {
  if (!maintenanceStore) {
    throw new Error("Maintenance store not initialized");
  }
  return maintenanceStore;
}

function asEnum<T extends string>(value: unknown, allowed: readonly T[]): T | undefined {
  if (typeof value !== "string") return undefined;
  return (allowed as readonly string[]).includes(value) ? (value as T) : undefined;
}

function parsePositiveInt(value: unknown, fallback: number, min: number, max: number): number {
  const raw = typeof value === "string" || typeof value === "number" ? Number(value) : NaN;
  if (!Number.isFinite(raw)) return fallback;
  const n = Math.trunc(raw);
  if (n < min) return min;
  if (n > max) return max;
  return n;
}

// GET /admin/maintenance/tabs
adminMaintenanceRouter.get("/tabs", (_req: Request, res: Response) => {
  res.json([
    { id: "architecture", label: "Architecture Group", groupKey: "architecture" },
    { id: "platform", label: "Platform", groupKey: "platform" },
    { id: "observability", label: "Observability", groupKey: "observability" },
    { id: "security", label: "Security", groupKey: "security" },
    { id: "governance", label: "Governance", groupKey: "governance" },
  ]);
});

// GET /admin/maintenance/columns
adminMaintenanceRouter.get("/columns", (_req: Request, res: Response) => {
  try {
    res.json({ table: "maintenance_records", columns: getStore().tableColumns() });
  } catch (err) {
    res.status(503).json({ error: (err as Error).message });
  }
});

// GET /admin/maintenance/records
adminMaintenanceRouter.get("/records", (req: Request, res: Response) => {
  try {
    const status = asEnum<MaintenanceStatus>(req.query.status, ["open", "in_progress", "blocked", "resolved", "archived"]);
    const severity = asEnum<MaintenanceSeverity>(req.query.severity, ["low", "medium", "high", "critical"]);
    const priority = asEnum<MaintenancePriority>(req.query.priority, ["P0", "P1", "P2", "P3", "P4"]);

    const records = getStore().listRecords({
      groupKey: typeof req.query.groupKey === "string" ? req.query.groupKey : undefined,
      status,
      severity,
      priority,
      includeArchived: req.query.includeArchived === "true",
      limit: parsePositiveInt(req.query.limit, 100, 1, 500),
      offset: parsePositiveInt(req.query.offset, 0, 0, 100000),
    });

    res.json(records);
  } catch (err) {
    res.status(503).json({ error: (err as Error).message });
  }
});

// GET /admin/maintenance/architecture
adminMaintenanceRouter.get("/architecture", (req: Request, res: Response) => {
  try {
    const status = asEnum<MaintenanceStatus>(req.query.status, ["open", "in_progress", "blocked", "resolved", "archived"]);
    const records = getStore().listRecords({
      groupKey: "architecture",
      status,
      includeArchived: req.query.includeArchived === "true",
      limit: parsePositiveInt(req.query.limit, 200, 1, 500),
      offset: parsePositiveInt(req.query.offset, 0, 0, 100000),
    });

    res.json(records);
  } catch (err) {
    res.status(503).json({ error: (err as Error).message });
  }
});

// GET /admin/maintenance/summary
adminMaintenanceRouter.get("/summary", (req: Request, res: Response) => {
  try {
    const groupKey = typeof req.query.groupKey === "string" ? req.query.groupKey : undefined;
    res.json(getStore().groupSummary(groupKey));
  } catch (err) {
    res.status(503).json({ error: (err as Error).message });
  }
});

// POST /admin/maintenance/analytics/recompute
adminMaintenanceRouter.post("/analytics/recompute", (req: Request, res: Response) => {
  try {
    const body = (req.body ?? {}) as { groupKey?: unknown };
    const groupKey = typeof body.groupKey === "string" ? body.groupKey : undefined;
    const result = getStore().recomputeAnalytics(groupKey);
    return res.json({ ok: true, ...result, groupKey: groupKey ?? null });
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// GET /admin/maintenance/analytics/overview?groupKey=architecture
adminMaintenanceRouter.get("/analytics/overview", (req: Request, res: Response) => {
  try {
    const groupKey = typeof req.query.groupKey === "string" ? req.query.groupKey : undefined;
    const overview = getStore().analyticsOverview(groupKey);
    return res.json({ groupKey: groupKey ?? null, ...overview });
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// GET /admin/maintenance/intelligence?groupKey=architecture
adminMaintenanceRouter.get("/intelligence", (req: Request, res: Response) => {
  try {
    const groupKey = typeof req.query.groupKey === "string" ? req.query.groupKey : "architecture";
    const report = getStore().getIntelligenceReport(groupKey);
    return res.json(report);
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// POST /admin/maintenance/intelligence/daily-review
adminMaintenanceRouter.post("/intelligence/daily-review", (req: Request, res: Response) => {
  try {
    const body = (req.body ?? {}) as {
      groupKey?: unknown;
      reviewerRole?: unknown;
      reviewDate?: unknown;
    };

    const groupKey = typeof body.groupKey === "string" ? body.groupKey : "architecture";
    const reviewerRole = typeof body.reviewerRole === "string" ? body.reviewerRole : "architecture_director";
    const reviewDate = typeof body.reviewDate === "string" ? body.reviewDate : undefined;

    const review = getStore().generateDailyReview(groupKey, reviewerRole, reviewDate);
    return res.json({ ok: true, review });
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// GET /admin/maintenance/intelligence/daily-reviews?groupKey=architecture&reviewerRole=architecture_director&limit=14
adminMaintenanceRouter.get("/intelligence/daily-reviews", (req: Request, res: Response) => {
  try {
    const groupKey = typeof req.query.groupKey === "string" ? req.query.groupKey : "architecture";
    const reviewerRole = typeof req.query.reviewerRole === "string" ? req.query.reviewerRole : "architecture_director";
    const limit = parsePositiveInt(req.query.limit, 14, 1, 90);
    const reviews = getStore().listDailyReviews(groupKey, reviewerRole, limit);
    return res.json(reviews);
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// GET /admin/maintenance/intelligence/trends?groupKey=architecture&reviewerRole=architecture_director
adminMaintenanceRouter.get("/intelligence/trends", (req: Request, res: Response) => {
  try {
    const groupKey = typeof req.query.groupKey === "string" ? req.query.groupKey : "architecture";
    const reviewerRole = typeof req.query.reviewerRole === "string" ? req.query.reviewerRole : "architecture_director";
    const trends = getStore().intelligenceTrends(groupKey, reviewerRole);
    return res.json(trends);
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// GET /admin/maintenance/intelligence/independent-eval?groupKey=architecture&reviewDate=YYYY-MM-DD
adminMaintenanceRouter.get("/intelligence/independent-eval", (req: Request, res: Response) => {
  try {
    const groupKey = typeof req.query.groupKey === "string" ? req.query.groupKey : "architecture";
    const reviewDate = typeof req.query.reviewDate === "string" ? req.query.reviewDate : undefined;
    const summary = getStore().getIndependentEvaluation(groupKey, reviewDate);
    return res.json(summary);
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// GET /admin/maintenance/intelligence/offline-audit
adminMaintenanceRouter.get("/intelligence/offline-audit", (_req: Request, res: Response) => {
  try {
    const latest = readLatestOfflineValueAudit();
    return res.json({
      enabled: isOfflineAuditEnabled(),
      available: Boolean(latest),
      latest,
    });
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// POST /admin/maintenance/intelligence/offline-audit/run
adminMaintenanceRouter.post("/intelligence/offline-audit/run", async (req: Request, res: Response) => {
  try {
    if (!isOfflineAuditEnabled()) {
      return res.status(409).json({
        error: "Offline audit mode is disabled by runtime controls",
      });
    }

    const body = (req.body ?? {}) as {
      sampleCount?: unknown;
      maxFileBytes?: unknown;
      model?: unknown;
    };

    const sampleCount = typeof body.sampleCount === "number" ? body.sampleCount : undefined;
    const maxFileBytes = typeof body.maxFileBytes === "number" ? body.maxFileBytes : undefined;
    const model = typeof body.model === "string" ? body.model : undefined;

    const report = await runOfflineValueAudit({ sampleCount, maxFileBytes, model });
    return res.json({ ok: true, report });
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// GET /admin/maintenance/intelligence/weekly-rollup?groupKey=architecture&reviewerRole=architecture_director&endDate=YYYY-MM-DD
adminMaintenanceRouter.get("/intelligence/weekly-rollup", (req: Request, res: Response) => {
  try {
    const groupKey = typeof req.query.groupKey === "string" ? req.query.groupKey : "architecture";
    const reviewerRole = typeof req.query.reviewerRole === "string" ? req.query.reviewerRole : "architecture_director";
    const endDate = typeof req.query.endDate === "string" ? req.query.endDate : undefined;
    const rollup = getStore().getWeeklyIndependentRollup(groupKey, reviewerRole, endDate);
    return res.json(rollup);
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// POST /admin/maintenance/intelligence/export-weekly
adminMaintenanceRouter.post("/intelligence/export-weekly", (req: Request, res: Response) => {
  try {
    const body = (req.body ?? {}) as {
      groupKey?: unknown;
      reviewerRole?: unknown;
      endDate?: unknown;
    };
    const groupKey = typeof body.groupKey === "string" ? body.groupKey : "architecture";
    const reviewerRole = typeof body.reviewerRole === "string" ? body.reviewerRole : "architecture_director";
    const endDate = typeof body.endDate === "string" ? body.endDate : undefined;
    const out = getStore().exportWeeklyIndependentRollupArtifact(groupKey, reviewerRole, endDate);
    return res.json({ ok: true, export: out });
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// POST /admin/maintenance/intelligence/export-daily
adminMaintenanceRouter.post("/intelligence/export-daily", (req: Request, res: Response) => {
  try {
    const body = (req.body ?? {}) as {
      groupKey?: unknown;
      reviewerRole?: unknown;
      reviewDate?: unknown;
    };

    const groupKey = typeof body.groupKey === "string" ? body.groupKey : "architecture";
    const reviewerRole = typeof body.reviewerRole === "string" ? body.reviewerRole : "architecture_director";
    const reviewDate = typeof body.reviewDate === "string" ? body.reviewDate : undefined;

    const result = getStore().exportDailyReviewArtifact(groupKey, reviewerRole, reviewDate);
    return res.json({ ok: true, export: result });
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// POST /admin/maintenance/records
adminMaintenanceRouter.post("/records", (req: Request, res: Response) => {
  try {
    const body = (req.body ?? {}) as Partial<CreateMaintenanceRecordInput>;

    if (!body.groupKey || !body.category || !body.title) {
      return res.status(400).json({
        error: "Body must include groupKey, category, and title",
      });
    }

    const severity = asEnum<MaintenanceSeverity>(body.severity, ["low", "medium", "high", "critical"]);
    const priority = asEnum<MaintenancePriority>(body.priority, ["P0", "P1", "P2", "P3", "P4"]);
    const status = asEnum<MaintenanceStatus>(body.status, ["open", "in_progress", "blocked", "resolved", "archived"]);
    const confidence = asEnum<MaintenanceConfidence>(body.confidence, ["observed", "strong_inference", "weak_inference", "unknown"]);

    const created = getStore().createRecord({
      groupKey: body.groupKey,
      category: body.category,
      title: body.title,
      summary: body.summary,
      severity,
      priority,
      status,
      confidence,
      source: body.source,
      sourceRef: body.sourceRef,
      workflowId: body.workflowId,
      component: body.component,
      environment: body.environment,
      ownerRole: body.ownerRole,
      assignee: body.assignee,
      dueDate: body.dueDate,
      sessionId: body.sessionId,
      taskId: body.taskId,
      impactScore: body.impactScore,
      effortScore: body.effortScore,
      riskScore: body.riskScore,
      evidenceJson: body.evidenceJson,
      recommendationJson: body.recommendationJson,
      tagsJson: body.tagsJson,
    });

    return res.status(201).json(created);
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

// PATCH /admin/maintenance/records/:id
adminMaintenanceRouter.patch("/records/:id", (req: Request, res: Response) => {
  try {
    const body = (req.body ?? {}) as Partial<CreateMaintenanceRecordInput> & { isArchived?: boolean };

    const severity = asEnum<MaintenanceSeverity>(body.severity, ["low", "medium", "high", "critical"]);
    const priority = asEnum<MaintenancePriority>(body.priority, ["P0", "P1", "P2", "P3", "P4"]);
    const status = asEnum<MaintenanceStatus>(body.status, ["open", "in_progress", "blocked", "resolved", "archived"]);
    const confidence = asEnum<MaintenanceConfidence>(body.confidence, ["observed", "strong_inference", "weak_inference", "unknown"]);

    const updated = getStore().updateRecord(req.params.id, {
      ...body,
      severity,
      priority,
      status,
      confidence,
    });

    if (!updated) {
      return res.status(404).json({ error: "Maintenance record not found" });
    }

    return res.json(updated);
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});
