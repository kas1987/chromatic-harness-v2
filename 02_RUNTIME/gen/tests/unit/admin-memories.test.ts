import { describe, it, expect, beforeEach, vi } from "vitest";
import express from "express";
import request from "supertest";
import type { MemoryItem } from "../../src/memory/memory-types";
import type { AdminMemoryService } from "../../src/services/admin-memory-service";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMemoryItem(overrides: Partial<MemoryItem> = {}): MemoryItem {
  return {
    id: "mem-abc123" as any,
    projectId: "proj-1" as any,
    ownerUserId: null,
    authorAgentId: "agent-1" as any,
    scope: "agent_private",
    kind: "fact",
    text: "test memory",
    sourceStepId: null,
    taskPurpose: null,
    sensitivity: "internal",
    createdAt: "2026-01-01T00:00:00.000Z",
    lastUsedAt: null,
    expiresAt: null,
    provenanceJson: null,
    ...overrides,
  };
}

// Mock AdminMemoryService — no native sqlite needed
function createMockAdminService(): AdminMemoryService {
  return {
    listMemories: vi.fn(),
    getMemory: vi.fn(),
    updateMemory: vi.fn(),
    deleteMemory: vi.fn(),
    scanConfidential: vi.fn(),
    findStale: vi.fn(),
    close: vi.fn(),
  } as unknown as AdminMemoryService;
}

// ---------------------------------------------------------------------------
// App factory — wires the admin router with the given service
// We import the router factories directly so we can inject the mock service.
// ---------------------------------------------------------------------------

async function buildApp(mockService: AdminMemoryService) {
  // Dynamically import the route module so we can call its initializer
  const { initializeAdminMemoriesRouter } = await import("../../src/routes/admin-memories");
  const { adminRouter } = await import("../../src/routes/admin-index");

  initializeAdminMemoriesRouter(mockService);

  const app = express();
  app.use(express.json());
  app.use("/admin", adminRouter);
  return app;
}

const ADMIN_CRED = "test-admin-secret";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Admin Memories API", () => {
  let mockService: AdminMemoryService;
  let app: express.Application;

  beforeEach(async () => {
    // Reset module registry so each test gets a fresh router state
    vi.resetModules();
    process.env.GEN_ADMIN_CRED = ADMIN_CRED;

    // Re-import after resetModules to pick up fresh module state
    const { initializeAdminMemoriesRouter } = await import("../../src/routes/admin-memories");
    const { adminRouter } = await import("../../src/routes/admin-index");

    mockService = createMockAdminService();
    initializeAdminMemoriesRouter(mockService);

    app = express();
    app.use(express.json());
    app.use("/admin", adminRouter);
  });

  // --- Auth ---

  it("returns 401 when X-Admin-Token header is missing", async () => {
    const res = await request(app).get("/admin/memories");
    expect(res.status).toBe(401);
    expect(res.body.error).toBe("Unauthorized");
  });

  it("returns 401 when X-Admin-Token header has wrong value", async () => {
    const res = await request(app)
      .get("/admin/memories")
      .set("X-Admin-Token", "wrong-token");
    expect(res.status).toBe(401);
    expect(res.body.error).toBe("Unauthorized");
  });

  it("passes through with correct X-Admin-Token", async () => {
    vi.mocked(mockService.listMemories).mockReturnValue({ items: [], total: 0 });

    const res = await request(app)
      .get("/admin/memories")
      .set("X-Admin-Token", ADMIN_CRED);
    expect(res.status).toBe(200);
  });

  // --- GET /admin/memories ---

  it("GET /admin/memories returns paginated list with defaults", async () => {
    const item = makeMemoryItem();
    vi.mocked(mockService.listMemories).mockReturnValue({ items: [item], total: 1 });

    const res = await request(app)
      .get("/admin/memories")
      .set("X-Admin-Token", ADMIN_CRED);

    expect(res.status).toBe(200);
    expect(res.body.items).toHaveLength(1);
    expect(res.body.total).toBe(1);
    expect(res.body.limit).toBe(50);
    expect(res.body.offset).toBe(0);
    expect(mockService.listMemories).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 50, offset: 0 })
    );
  });

  it("GET /admin/memories passes limit and offset from query params", async () => {
    vi.mocked(mockService.listMemories).mockReturnValue({ items: [], total: 0 });

    await request(app)
      .get("/admin/memories?limit=10&offset=20")
      .set("X-Admin-Token", ADMIN_CRED);

    expect(mockService.listMemories).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 10, offset: 20 })
    );
  });

  it("GET /admin/memories passes sensitivity filter", async () => {
    vi.mocked(mockService.listMemories).mockReturnValue({ items: [], total: 0 });

    await request(app)
      .get("/admin/memories?sensitivity=confidential")
      .set("X-Admin-Token", ADMIN_CRED);

    expect(mockService.listMemories).toHaveBeenCalledWith(
      expect.objectContaining({ sensitivity: "confidential" })
    );
  });

  it("GET /admin/memories passes projectId filter", async () => {
    vi.mocked(mockService.listMemories).mockReturnValue({ items: [], total: 0 });

    await request(app)
      .get("/admin/memories?projectId=proj-42")
      .set("X-Admin-Token", ADMIN_CRED);

    expect(mockService.listMemories).toHaveBeenCalledWith(
      expect.objectContaining({ projectId: "proj-42" })
    );
  });

  it("GET /admin/memories returns 500 on service error", async () => {
    vi.mocked(mockService.listMemories).mockImplementation(() => {
      throw new Error("DB failure");
    });

    const res = await request(app)
      .get("/admin/memories")
      .set("X-Admin-Token", ADMIN_CRED);

    expect(res.status).toBe(500);
  });

  // --- GET /admin/memories/:id ---

  it("GET /admin/memories/:id returns the memory", async () => {
    const item = makeMemoryItem({ id: "mem-xyz" as any, text: "specific memory" });
    vi.mocked(mockService.getMemory).mockReturnValue(item);

    const res = await request(app)
      .get("/admin/memories/mem-xyz")
      .set("X-Admin-Token", ADMIN_CRED);

    expect(res.status).toBe(200);
    expect(res.body.id).toBe("mem-xyz");
    expect(res.body.text).toBe("specific memory");
    expect(mockService.getMemory).toHaveBeenCalledWith("mem-xyz");
  });

  it("GET /admin/memories/:id returns 404 when memory not found", async () => {
    vi.mocked(mockService.getMemory).mockReturnValue(null);

    const res = await request(app)
      .get("/admin/memories/does-not-exist")
      .set("X-Admin-Token", ADMIN_CRED);

    expect(res.status).toBe(404);
    expect(res.body.error).toBe("Memory not found");
  });

  it("GET /admin/memories/:id returns 500 on service error", async () => {
    vi.mocked(mockService.getMemory).mockImplementation(() => {
      throw new Error("boom");
    });

    const res = await request(app)
      .get("/admin/memories/mem-xyz")
      .set("X-Admin-Token", ADMIN_CRED);

    expect(res.status).toBe(500);
  });

  // --- PATCH /admin/memories/:id ---

  it("PATCH /admin/memories/:id updates and returns the memory", async () => {
    const updated = makeMemoryItem({ text: "updated text" });
    vi.mocked(mockService.updateMemory).mockReturnValue(updated);

    const res = await request(app)
      .patch("/admin/memories/mem-abc123")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({ text: "updated text" });

    expect(res.status).toBe(200);
    expect(res.body.text).toBe("updated text");
    expect(mockService.updateMemory).toHaveBeenCalledWith(
      "mem-abc123",
      expect.objectContaining({ text: "updated text" })
    );
  });

  it("PATCH /admin/memories/:id sends sensitivity and expiresAt patches", async () => {
    const updated = makeMemoryItem({ sensitivity: "confidential", expiresAt: "2099-01-01T00:00:00.000Z" });
    vi.mocked(mockService.updateMemory).mockReturnValue(updated);

    const res = await request(app)
      .patch("/admin/memories/mem-abc123")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({ sensitivity: "confidential", expiresAt: "2099-01-01T00:00:00.000Z" });

    expect(res.status).toBe(200);
    expect(mockService.updateMemory).toHaveBeenCalledWith(
      "mem-abc123",
      expect.objectContaining({ sensitivity: "confidential", expiresAt: "2099-01-01T00:00:00.000Z" })
    );
  });

  it("PATCH /admin/memories/:id returns 404 when service throws not-found", async () => {
    vi.mocked(mockService.updateMemory).mockImplementation(() => {
      throw new Error("Memory not found: mem-ghost");
    });

    const res = await request(app)
      .patch("/admin/memories/mem-ghost")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({ text: "noop" });

    expect(res.status).toBe(404);
  });

  it("PATCH /admin/memories/:id returns 500 on unexpected service error", async () => {
    vi.mocked(mockService.updateMemory).mockImplementation(() => {
      throw new Error("unexpected failure");
    });

    const res = await request(app)
      .patch("/admin/memories/mem-abc123")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({ text: "noop" });

    expect(res.status).toBe(500);
  });

  // --- DELETE /admin/memories/:id ---

  it("DELETE /admin/memories/:id soft-deletes and returns 204", async () => {
    vi.mocked(mockService.deleteMemory).mockReturnValue(undefined);

    const res = await request(app)
      .delete("/admin/memories/mem-abc123")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({ reason: "test cleanup" });

    expect(res.status).toBe(204);
    expect(mockService.deleteMemory).toHaveBeenCalledWith("mem-abc123", "test cleanup");
  });

  it("DELETE /admin/memories/:id returns 400 when reason is missing", async () => {
    const res = await request(app)
      .delete("/admin/memories/mem-abc123")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({});

    expect(res.status).toBe(400);
    expect(res.body.error).toBe("reason is required");
    expect(mockService.deleteMemory).not.toHaveBeenCalled();
  });

  it("DELETE /admin/memories/:id returns 400 when reason is whitespace only", async () => {
    const res = await request(app)
      .delete("/admin/memories/mem-abc123")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({ reason: "   " });

    expect(res.status).toBe(400);
    expect(mockService.deleteMemory).not.toHaveBeenCalled();
  });

  it("DELETE /admin/memories/:id returns 404 when service throws not-found", async () => {
    vi.mocked(mockService.deleteMemory).mockImplementation(() => {
      throw new Error("Memory not found: mem-ghost");
    });

    const res = await request(app)
      .delete("/admin/memories/mem-ghost")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({ reason: "cleanup" });

    expect(res.status).toBe(404);
  });

  // --- POST /admin/memories/scan-confidential ---

  it("POST /admin/memories/scan-confidential returns confidential items", async () => {
    const items = [makeMemoryItem({ sensitivity: "confidential" })];
    vi.mocked(mockService.scanConfidential).mockReturnValue(items);

    const res = await request(app)
      .post("/admin/memories/scan-confidential")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({});

    expect(res.status).toBe(200);
    expect(res.body.count).toBe(1);
    expect(res.body.items[0].sensitivity).toBe("confidential");
    expect(mockService.scanConfidential).toHaveBeenCalledWith(undefined);
  });

  it("POST /admin/memories/scan-confidential passes projectId when provided", async () => {
    vi.mocked(mockService.scanConfidential).mockReturnValue([]);

    await request(app)
      .post("/admin/memories/scan-confidential")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({ projectId: "proj-42" });

    expect(mockService.scanConfidential).toHaveBeenCalledWith("proj-42");
  });

  it("POST /admin/memories/scan-confidential returns 500 on service error", async () => {
    vi.mocked(mockService.scanConfidential).mockImplementation(() => {
      throw new Error("boom");
    });

    const res = await request(app)
      .post("/admin/memories/scan-confidential")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({});

    expect(res.status).toBe(500);
  });

  // --- POST /admin/memories/find-stale ---

  it("POST /admin/memories/find-stale returns stale items", async () => {
    const items = [makeMemoryItem()];
    vi.mocked(mockService.findStale).mockReturnValue(items);

    const res = await request(app)
      .post("/admin/memories/find-stale")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({ olderThanDays: 30 });

    expect(res.status).toBe(200);
    expect(res.body.count).toBe(1);
    expect(mockService.findStale).toHaveBeenCalledWith(30);
  });

  it("POST /admin/memories/find-stale returns 400 when olderThanDays is missing", async () => {
    const res = await request(app)
      .post("/admin/memories/find-stale")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({});

    expect(res.status).toBe(400);
    expect(res.body.error).toBeDefined();
    expect(mockService.findStale).not.toHaveBeenCalled();
  });

  it("POST /admin/memories/find-stale returns 400 when olderThanDays is zero", async () => {
    const res = await request(app)
      .post("/admin/memories/find-stale")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({ olderThanDays: 0 });

    expect(res.status).toBe(400);
    expect(mockService.findStale).not.toHaveBeenCalled();
  });

  it("POST /admin/memories/find-stale returns 400 when olderThanDays is negative", async () => {
    const res = await request(app)
      .post("/admin/memories/find-stale")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({ olderThanDays: -5 });

    expect(res.status).toBe(400);
    expect(mockService.findStale).not.toHaveBeenCalled();
  });

  it("POST /admin/memories/find-stale returns 500 on service error", async () => {
    vi.mocked(mockService.findStale).mockImplementation(() => {
      throw new Error("boom");
    });

    const res = await request(app)
      .post("/admin/memories/find-stale")
      .set("X-Admin-Token", ADMIN_CRED)
      .send({ olderThanDays: 7 });

    expect(res.status).toBe(500);
  });
});
