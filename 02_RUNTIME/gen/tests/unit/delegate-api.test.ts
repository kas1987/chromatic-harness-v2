import { describe, it, expect, beforeEach, afterEach } from "vitest";
import express from "express";
import request from "supertest";
import Database from "better-sqlite3";
import fs from "fs";
import os from "os";
import path from "path";
import { authMiddleware } from "../../src/middleware/auth";
import { delegateRouter, initializeDelegateRouter } from "../../src/routes/delegate";

describe("Delegate API (mounted)", () => {
  let app: express.Application;
  let dbPath: string;
  let prevToken: string | undefined;

  beforeEach(() => {
    prevToken = process.env.GEN_TOKEN;
    process.env.GEN_TOKEN = "delegate-api-test-token-unique";

    dbPath = path.join(os.tmpdir(), `gen-delegate-test-${Date.now()}.db`);
    const db = new Database(dbPath);
    initializeDelegateRouter(db);

    app = express();
    app.use(express.json());
    app.use(authMiddleware);
    app.use("/api/delegate", delegateRouter);
  });

  afterEach(() => {
    if (prevToken === undefined) {
      delete process.env.GEN_TOKEN;
    } else {
      process.env.GEN_TOKEN = prevToken;
    }
    try {
      fs.unlinkSync(dbPath);
    } catch {
      /* ignore */
    }
  });

  it("POST /api/delegate without prompt returns 400", async () => {
    const res = await request(app)
      .post("/api/delegate")
      .set("Authorization", "Bearer delegate-api-test-token-unique")
      .send({});
    expect(res.status).toBe(400);
  });

  it("POST /api/delegate with unknown role returns 400", async () => {
    const res = await request(app)
      .post("/api/delegate")
      .set("Authorization", "Bearer delegate-api-test-token-unique")
      .send({ prompt: "hello", role: "__nonexistent_role__" });
    expect(res.status).toBe(400);
    expect(res.body.available).toBeDefined();
  });

  it("GET /api/delegate/roles returns role registry", async () => {
    const res = await request(app)
      .get("/api/delegate/roles")
      .set("Authorization", "Bearer delegate-api-test-token-unique");
    expect(res.status).toBe(200);
    expect(typeof res.body).toBe("object");
    expect(Object.keys(res.body).length).toBeGreaterThan(0);
  });

  it("GET /api/delegate/queue returns queue stats", async () => {
    const res = await request(app)
      .get("/api/delegate/queue")
      .set("Authorization", "Bearer delegate-api-test-token-unique");
    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty("pending");
  });
});
