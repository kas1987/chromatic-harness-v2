import { Request, Response, Router } from "express";
import { MetaBrainStore, type CreateMetaBrainEntryInput, type MetaBrainSourceType } from "../meta-brain/meta-brain-store";

export const adminMetaBrainRouter = Router();

let metaBrainStore: MetaBrainStore | null = null;

export function initializeAdminMetaBrainRouter(store: MetaBrainStore): void {
  metaBrainStore = store;
}

function getStore(): MetaBrainStore {
  if (!metaBrainStore) {
    throw new Error("Meta-brain store not initialized");
  }
  return metaBrainStore;
}

function asSourceType(value: unknown): MetaBrainSourceType | undefined {
  if (typeof value !== "string") return undefined;
  const allowed: MetaBrainSourceType[] = ["log", "knowledge", "finding", "review", "event"];
  return allowed.includes(value as MetaBrainSourceType) ? (value as MetaBrainSourceType) : undefined;
}

adminMetaBrainRouter.get("/entries", (req: Request, res: Response) => {
  try {
    const entries = getStore().listEntries({
      repoKey: typeof req.query.repoKey === "string" ? req.query.repoKey : undefined,
      userKey: typeof req.query.userKey === "string" ? req.query.userKey : undefined,
      sourceTeam: typeof req.query.sourceTeam === "string" ? req.query.sourceTeam : undefined,
      sourceType: asSourceType(req.query.sourceType),
      limit: req.query.limit ? parseInt(String(req.query.limit), 10) : 100,
      offset: req.query.offset ? parseInt(String(req.query.offset), 10) : 0,
    });
    return res.json(entries);
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

adminMetaBrainRouter.get("/summary", (req: Request, res: Response) => {
  try {
    const repoKey = typeof req.query.repoKey === "string" ? req.query.repoKey : undefined;
    const userKey = typeof req.query.userKey === "string" ? req.query.userKey : undefined;
    return res.json(getStore().summary(repoKey, userKey));
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

adminMetaBrainRouter.post("/entries", (req: Request, res: Response) => {
  try {
    const body = (req.body ?? {}) as Partial<CreateMetaBrainEntryInput>;

    if (!body.sourceTeam || !body.sourceType || !body.repoKey || !body.userKey || !body.title || !body.content) {
      return res.status(400).json({
        error: "Body must include sourceTeam, sourceType, repoKey, userKey, title, and content",
      });
    }

    const sourceType = asSourceType(body.sourceType);
    if (!sourceType) {
      return res.status(400).json({ error: "Invalid sourceType" });
    }

    const created = getStore().createEntry({
      sourceTeam: body.sourceTeam,
      sourceType,
      repoKey: body.repoKey,
      userKey: body.userKey,
      sessionId: body.sessionId,
      title: body.title,
      content: body.content,
      confidence: body.confidence,
      tagsJson: body.tagsJson,
      metadataJson: body.metadataJson,
      eventTs: body.eventTs,
      sourceKey: body.sourceKey,
    });

    return res.status(201).json(created);
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

adminMetaBrainRouter.post("/entries/batch", (req: Request, res: Response) => {
  try {
    const body = (req.body ?? {}) as { entries?: unknown[] };
    if (!Array.isArray(body.entries) || body.entries.length === 0) {
      return res.status(400).json({ error: "Body must include a non-empty entries array" });
    }

    const created = [];
    for (const raw of body.entries) {
      const item = raw as Partial<CreateMetaBrainEntryInput>;
      if (!item.sourceTeam || !item.sourceType || !item.repoKey || !item.userKey || !item.title || !item.content) {
        continue;
      }
      const sourceType = asSourceType(item.sourceType);
      if (!sourceType) continue;

      created.push(
        getStore().createEntry({
          sourceTeam: item.sourceTeam,
          sourceType,
          repoKey: item.repoKey,
          userKey: item.userKey,
          sessionId: item.sessionId,
          title: item.title,
          content: item.content,
          confidence: item.confidence,
          tagsJson: item.tagsJson,
          metadataJson: item.metadataJson,
          eventTs: item.eventTs,
          sourceKey: item.sourceKey,
        }),
      );
    }

    return res.json({ ok: true, created: created.length, entries: created });
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});

adminMetaBrainRouter.post("/consolidate/internal", (req: Request, res: Response) => {
  try {
    const body = (req.body ?? {}) as { repoKey?: unknown; userKey?: unknown };
    const repoKey = typeof body.repoKey === "string" ? body.repoKey : "04-prism";
    const userKey = typeof body.userKey === "string" ? body.userKey : "default-user";
    const result = getStore().consolidateInternalSources(repoKey, userKey);
    return res.json({ ok: true, ...result, repoKey, userKey });
  } catch (err) {
    return res.status(503).json({ error: (err as Error).message });
  }
});
