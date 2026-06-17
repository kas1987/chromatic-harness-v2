import { afterEach, beforeEach, describe, expect, it } from "vitest";
import express from "express";
import request from "supertest";
import { authMiddleware } from "../../src/middleware/auth";
import { initializeSandboxOlRouter, sandboxOlRouter } from "../../src/routes/sandbox-ol";

describe("Sandbox OL API (mounted)", () => {
  let app: express.Application;
  let prevCred: string | undefined;

  beforeEach(() => {
    prevCred = process.env["GEN_TOKEN"];
    process.env["GEN_TOKEN"] = "sandbox-ol-test-token";

    initializeSandboxOlRouter(null);

    app = express();
    app.use(express.json());
    app.use(authMiddleware);
    app.use("/api/sandbox-ol", sandboxOlRouter);
  });

  afterEach(() => {
    if (prevCred === undefined) {
      delete process.env["GEN_TOKEN"];
      return;
    }
    process.env["GEN_TOKEN"] = prevCred;
  });

  it("GET /api/sandbox-ol/agents returns allowlist", async () => {
    const res = await request(app)
      .get("/api/sandbox-ol/agents")
      .set("Authorization", "Bearer sandbox-ol-test-token");

    expect(res.status).toBe(200);
    expect(Array.isArray(res.body.agents)).toBe(true);
    expect(res.body.agents.length).toBeGreaterThan(0);
  });

  it("POST /api/sandbox-ol/delegate rejects unknown agents", async () => {
    const res = await request(app)
      .post("/api/sandbox-ol/delegate")
      .set("Authorization", "Bearer sandbox-ol-test-token")
      .send({ agent: "unknown", prompt: "hello" });

    expect(res.status).toBe(400);
    expect(Array.isArray(res.body.allowedAgents)).toBe(true);
  });

  it("POST /api/sandbox-ol/delegate requires prompt", async () => {
    const res = await request(app)
      .post("/api/sandbox-ol/delegate")
      .set("Authorization", "Bearer sandbox-ol-test-token")
      .send({ agent: "planner" });

    expect(res.status).toBe(400);
    expect(String(res.body.error)).toContain("prompt");
  });
});
